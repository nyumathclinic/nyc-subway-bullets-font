"""
Turn a Commons bullet SVG into colored layers in font coordinates.

Some files need cleaning up first, because picosvg accepts neither text nor
style sheets:

  * empty <text> elements (left over in many Inkscape files) are removed;
  * a file with real text is converted to outlines by Inkscape, once; the
    result is kept in sources/outlined/ (and committed), so rebuilding
    needs neither Inkscape nor the fonts the text was set in;
  * fill="currentColor" is replaced by the inherited `color`;
  * the rules of a <style> sheet (Illustrator exports) are inlined.

picosvg then
reduces each SVG to a flat list of filled paths: circles, polygons,
strokes, transforms and so on are all converted to plain path data.  We then

  * drop invisible shapes (fill="none", zero opacity);
  * scale and translate the artwork into font units, flipping the y axis;
  * remove overlaps with skia-pathops, so each layer is a clean,
    non-overlapping, clockwise TrueType-style outline.

Scaling.  Every bullet is scaled by its own height: circles (and any other
non-diamond shape) become CIRCLE_HEIGHT font units tall, diamonds
DIAMOND_HEIGHT.  The source files can't be trusted to agree on this: the
NYCTA set alone uses seven page sizes, and draws some diamonds as tall as
its circles and others larger.

Each glyph is centered vertically on CENTER_Y and horizontally within its
advance, which is its width plus SIDE_BEARING on each side.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pathops
from fontTools.pens.transformPen import TransformPen
from fontTools.svgLib.path import parse_path
from lxml import etree
from picosvg.svg import SVG
from picosvg.svg_types import SVGPath

from .config import OUTLINED_DIR

UPM = 1000
CIRCLE_HEIGHT = 800
# Diamond bullets are about 1.2 times as tall as circles in both the
# Standard and Helvetica sets.
DIAMOND_HEIGHT = 960
CENTER_Y = 300
SIDE_BEARING = 50

Color = tuple[int, int, int, int]  # 0..255 RGBA


@dataclass
class Layer:
    path: pathops.Path   # in font units, y up
    color: Color


@dataclass
class Bullet:
    layers: list[Layer]
    advance: int


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

NAMED = {
    "white": "#ffffff", "black": "#000000", "red": "#ff0000",
    "yellow": "#ffff00", "blue": "#0000ff", "gray": "#808080",
    "grey": "#808080", "orange": "#ffa500", "green": "#008000",
}

RGB_RE = re.compile(r"rgba?\(([^)]*)\)")


def parse_color(fill: str, opacity: float) -> Color | None:
    fill = NAMED.get(fill.strip().lower(), fill.strip().lower())
    if fill in ("none", "transparent", ""):
        return None
    if m := RGB_RE.fullmatch(fill):
        parts = [p.strip() for p in m.group(1).split(",")]
        r, g, b = (
            round(float(p[:-1]) * 2.55) if p.endswith("%") else int(float(p))
            for p in parts[:3]
        )
        a = round(float(parts[3]) * 255) if len(parts) > 3 else 255
    elif fill.startswith("#"):
        h = fill[1:]
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        a = int(h[6:8], 16) if len(h) == 8 else 255
    else:
        raise ValueError(f"unsupported fill {fill!r}")
    a = round(a * opacity)
    if a == 0:
        return None
    return r, g, b, a


@dataclass
class Source:
    """A parsed SVG in its own coordinates (y down)."""

    view_box: tuple[float, float]
    shapes: list[tuple[str, str, Color]]   # (path data, fill rule, color)
    bbox: tuple[float, float, float, float]  # xmin, ymin, xmax, ymax

    @property
    def fill_ratio(self) -> float:
        """The fraction of the bounding box covered by the artwork."""

        union = pathops.Path()
        for d, _, _ in self.shapes:
            path = pathops.Path()
            parse_path(d, path.getPen())
            union = pathops.op(union, path, pathops.PathOp.UNION)
        xmin, ymin, xmax, ymax = self.bbox
        return union.area / ((xmax - xmin) * (ymax - ymin))

    @property
    def is_diamond(self) -> bool:
        """A diamond fills half its bounding box, a circle 78.5%."""

        return self.fill_ratio < 0.65

    @property
    def background(self) -> Color:
        """The color of the largest shape: the circle or diamond."""

        def area(d: str) -> float:
            path = pathops.Path()
            parse_path(d, path.getPen())
            return abs(path.area)

        return max(self.shapes, key=lambda s: area(s[0]))[2]


SVG_NS = "{http://www.w3.org/2000/svg}"
CSS_RULE_RE = re.compile(r"([^{}]+)\{([^{}]*)\}")


INKSCAPE_APP = "/Applications/Inkscape.app/Contents/MacOS/inkscape"


def find_inkscape() -> str | None:
    for candidate in (os.environ.get("INKSCAPE"), shutil.which("inkscape"),
                      INKSCAPE_APP):
        if candidate and Path(candidate).exists():
            return candidate
    return None


def has_text(root) -> bool:
    return any(
        "".join(t.itertext()).strip()
        for t in root.iter(f"{SVG_NS}text")
    )


def outline_text(path: Path) -> Path:
    """
    The version of `path` with its text converted to outlines, from
    sources/outlined/, creating it with Inkscape if necessary.
    """

    outlined = OUTLINED_DIR / path.name
    if outlined.exists():
        return outlined

    inkscape = find_inkscape()
    if inkscape is None:
        raise RuntimeError(
            f"{path.name} contains text, which must be converted to outlines "
            f"with Inkscape: install it, or set INKSCAPE to its executable."
        )
    OUTLINED_DIR.mkdir(parents=True, exist_ok=True)
    print(f"  converting the text in {path.name} to outlines (Inkscape)")
    subprocess.run(
        [inkscape, "--export-text-to-path", "--export-plain-svg",
         "--export-type=svg", f"--export-filename={outlined}", str(path)],
        check=True, capture_output=True,
    )
    return outlined


def preprocess(path: Path) -> bytes:
    """Make an SVG palatable to picosvg (see the module docstring)."""

    parser = etree.XMLParser(remove_comments=True, resolve_entities=False)
    root = etree.parse(str(path), parser).getroot()

    if has_text(root):
        root = etree.parse(str(outline_text(path)), parser).getroot()
        if has_text(root):
            raise RuntimeError(f"{path.name}: text left after outlining")

    for t in list(root.iter(f"{SVG_NS}text")):
        t.getparent().remove(t)

    resolve_current_color(root)
    return inline_css(etree.tostring(root))


def _style(el) -> dict[str, str]:
    decls = (d.split(":", 1) for d in (el.get("style") or "").split(";") if ":" in d)
    return {k.strip(): v.strip() for k, v in decls}


def resolve_current_color(root) -> None:
    """Replace fill/stroke="currentColor" by the inherited `color` value."""

    def color_of(el) -> str:
        while el is not None:
            c = _style(el).get("color") or el.get("color")
            if c and c.lower() not in ("inherit", "currentcolor"):
                return c
            el = el.getparent()
        return "#000000"   # the initial value of `color`

    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        for prop in ("fill", "stroke"):
            if (el.get(prop) or "").lower() == "currentcolor":
                el.set(prop, color_of(el))
        style = _style(el)
        changed = False
        for prop in ("fill", "stroke"):
            if style.get(prop, "").lower() == "currentcolor":
                style[prop] = color_of(el)
                changed = True
        if changed:
            el.set("style", ";".join(f"{k}:{v}" for k, v in style.items()))


def inline_css(data: bytes) -> bytes:
    """
    Apply the rules of any <style> element to the elements they select, and
    remove the <style> elements (which picosvg does not accept).

    Only the simple selectors that SVG editors such as Illustrator write are
    supported: `.class`, `element` and comma-separated lists of these.
    """

    parser = etree.XMLParser(remove_comments=True, resolve_entities=False)
    root = etree.fromstring(data, parser)
    styles = root.findall(f".//{SVG_NS}style")
    if not styles:
        return data

    css = re.sub(r"/\*.*?\*/", "", "".join(s.text or "" for s in styles), flags=re.S)
    for selectors, body in CSS_RULE_RE.findall(css):
        decls = [d.split(":", 1) for d in body.split(";") if ":" in d]
        decls = [(k.strip(), v.strip()) for k, v in decls]
        for selector in (s.strip() for s in selectors.split(",")):
            if selector.startswith("."):
                cls = selector[1:]
                targets = [
                    el for el in root.iter()
                    if isinstance(el.tag, str)
                    and cls in (el.get("class") or "").split()
                ]
            elif re.fullmatch(r"[A-Za-z]+", selector):
                targets = list(root.iter(SVG_NS + selector))
            else:
                raise ValueError(f"unsupported CSS selector {selector!r}")
            for el in targets:
                for k, v in decls:
                    # A class rule overrides presentation attributes;
                    # an inline style attribute still overrides both.
                    el.set(k, v)

    for s in styles:
        s.getparent().remove(s)
    return etree.tostring(root)


@lru_cache(maxsize=None)
def load_source(path: Path) -> Source:
    svg = SVG.fromstring(preprocess(path).decode()).topicosvg()
    vb = svg.view_box()
    shapes = []
    xs, ys = [], []
    for shape in svg.shapes():
        assert isinstance(shape, SVGPath)
        color = parse_color(shape.fill, shape.opacity * shape.fill_opacity)
        if color is None:
            continue
        shapes.append((shape.d, shape.fill_rule, color))
        box = shape.bounding_box()
        xs += [box.x, box.x + box.w]
        ys += [box.y, box.y + box.h]
    if not shapes:
        raise ValueError(f"{path.name}: no visible shapes")
    return Source((vb.w, vb.h), shapes, (min(xs), min(ys), max(xs), max(ys)))


# ---------------------------------------------------------------------------
# Scaling
# ---------------------------------------------------------------------------

def scales(sources: dict[str, Source]) -> dict[str, float]:
    """
    The scale factor for each file: diamonds become DIAMOND_HEIGHT tall,
    everything else CIRCLE_HEIGHT.  Diamonds are recognized by their shape,
    since not every file name says so.
    """

    result = {}
    for name, src in sources.items():
        height = src.bbox[3] - src.bbox[1]
        target = DIAMOND_HEIGHT if src.is_diamond else CIRCLE_HEIGHT
        result[name] = target / height
    return result


# ---------------------------------------------------------------------------
# Conversion to font coordinates
# ---------------------------------------------------------------------------

def to_bullet(src: Source, scale: float) -> Bullet:
    xmin, ymin, xmax, ymax = src.bbox
    width = (xmax - xmin) * scale
    advance = round(width + 2 * SIDE_BEARING)

    cx = (xmin + xmax) / 2
    cy = (ymin + ymax) / 2
    # x' = (x - cx) * s + advance/2 ;  y' = CENTER_Y - (y - cy) * s
    transform = (
        scale, 0, 0, -scale,
        advance / 2 - cx * scale,
        CENTER_Y + cy * scale,
    )

    layers = []
    for d, fill_rule, color in src.shapes:
        path = pathops.Path()
        parse_path(d, TransformPen(path.getPen(), transform))
        if fill_rule == "evenodd":
            path.fillType = pathops.FillType.EVEN_ODD
        path.simplify(fix_winding=True, clockwise=True)
        layers.append(Layer(path, color))

    return Bullet(layers, advance)


def monochrome(bullet: Bullet) -> pathops.Path:
    """
    A single-color outline for renderers without color support.

    The first layer is the bullet's background shape.  Later layers in the
    same color extend it; layers in any other color (the lettering, whether
    white on blue or black on yellow) are cut out of it.
    """

    background = bullet.layers[0].color
    result = pathops.Path()
    for layer in bullet.layers:
        if layer.color == background:
            op = pathops.PathOp.UNION
        else:
            op = pathops.PathOp.DIFFERENCE
        result = pathops.op(result, layer.path, op,
                            fix_winding=True, clockwise=True)
    return result
