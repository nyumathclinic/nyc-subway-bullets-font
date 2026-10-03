"""
Build one OpenType color font per bullet set.

Each font has three representations of every bullet:

  glyf        a monochrome outline (background shape with the lettering cut
              out), for renderers without color support (e.g. XeLaTeX)
  COLR/CPAL   layered flat colors (COLR version 0), used by LuaLaTeX,
              Windows, Chrome, Firefox, ...
  SVG         the same layers as an SVG document, used by Safari/Core Text,
              Adobe applications, Firefox, ...

Both color tables are generated from the same normalized layers, so they
render identically.

Typing.  Each bullet has a Private Use Area code point (from the mapping
table) and a key such as F, Fd, SIRd or M.brown.  Every character used in a
key is mapped in the cmap; a character that is a key by itself (F, 7, -)
maps straight to its bullet, other characters (d, the dot, lower-case
letters) map to a hollow "unknown" box so that mistakes are visible.  The
multi-character keys are ligatures in a lookup that is registered under the
rlig, liga and calt features, so they work wherever ligatures do.  Within a
ligature lookup the longest match wins: SIRd beats SIR beats S.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pathops
from fontTools.agl import UV2AGL
from fontTools.colorLib.builder import buildCOLR, buildCPAL
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import newTable
from fontTools.ttLib.tables.S_V_G_ import SVGDocument

from . import mapping, svgnorm
from .config import FONT_DIR, SOURCE_DIR, BulletSet, load_config
from .credits import credits_for

VERSION = "0.100"
VENDOR = "NYCB"

SPACE_WIDTH = 250
UNKNOWN_WIDTH = 500

# A fixed date keeps rebuilds byte-identical (seconds since 1904-01-01).
TIMESTAMP = 3786825600  # 2024-01-01


# ---------------------------------------------------------------------------
# Glyph names
# ---------------------------------------------------------------------------

def glyph_name(key: str) -> str:
    """bullet.F, bullet.Fd, bullet.M.brown, bullet.dash, bullet.Ad.1979_1987"""

    if key.startswith("-"):
        key = "dash" + key[1:]
    return "bullet." + key.replace("-", "_")


def char_glyph_name(ch: str) -> str:
    return UV2AGL.get(ord(ch), f"uni{ord(ch):04X}")


# ---------------------------------------------------------------------------
# Outlines
# ---------------------------------------------------------------------------

def tt_glyph(path: pathops.Path | None):
    pen = TTGlyphPen(None)
    if path is not None:
        path.draw(Cu2QuPen(pen, max_err=1.0, reverse_direction=False))
    return pen.glyph()


def unknown_box() -> pathops.Path:
    """A hollow rectangle, for characters that aren't (part of) a key."""

    def rect(x0, y0, x1, y1, clockwise):
        pts = [(x0, y0), (x0, y1), (x1, y1), (x1, y0)]
        if not clockwise:
            pts.reverse()
        p = pathops.Path()
        pen = p.getPen()
        pen.moveTo(pts[0])
        for pt in pts[1:]:
            pen.lineTo(pt)
        pen.closePath()
        return p

    outer = rect(60, 0, UNKNOWN_WIDTH - 60, 700, True)
    inner = rect(110, 50, UNKNOWN_WIDTH - 110, 650, True)
    return pathops.op(outer, inner, pathops.PathOp.DIFFERENCE,
                      fix_winding=True, clockwise=True)


def svg_document(gid: int, bullet: svgnorm.Bullet) -> str:
    """An OT-SVG document for one glyph (SVG y axis points down)."""

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg"><g id="glyph{gid}">']
    for layer in bullet.layers:
        pen = SVGPathPen(None, ntos=lambda v: f"{v:.1f}".rstrip("0").rstrip("."))
        layer.path.draw(TransformPen(pen, (1, 0, 0, -1, 0, 0)))
        r, g, b, a = layer.color
        attrs = f'fill="#{r:02x}{g:02x}{b:02x}"'
        if a != 255:
            attrs += f' fill-opacity="{a / 255:.3f}"'
        parts.append(f'<path d="{pen.getCommands()}" {attrs}/>')
    parts.append("</g></svg>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# Font
# ---------------------------------------------------------------------------

def check_tables(sets: list[BulletSet]) -> dict[str, list[mapping.Row]]:
    tables = {}
    bad = False
    for bset in sets:
        rows = mapping.read_table(bset.mapping_file)
        if not rows:
            print(f"{bset.mapping_file}: missing or empty; run `nycbullets map`",
                  file=sys.stderr)
            bad = True
        for msg in mapping.problems(rows):
            print(f"{bset.mapping_file.name}: {msg}", file=sys.stderr)
            bad = True
        tables[bset.id] = rows
    if bad:
        raise SystemExit("Fix the mapping tables before building.")
    return tables


def copyright_notice(rows: list[mapping.Row]) -> str:
    notice = ("Bullet artwork: Metropolitan Transportation Authority; "
              "public domain, via Wikimedia Commons.")
    credits = credits_for({r.file for r in rows})
    if credits:
        notice += " Also contains: " + "; ".join(map(str, credits)) + "."
    return notice


def license_notice(rows: list[mapping.Row]) -> str:
    credits = credits_for({r.file for r in rows})
    notice = ("The bullet artwork is from "
              "https://commons.wikimedia.org/wiki/"
              "Category:New_York_City_Subway_bullets and is in the public "
              "domain")
    if credits:
        notice += (", except for the bullets credited in the copyright "
                   "notice, which are used under the licenses stated there")
    return notice + "."


def write_credits(fonts: list[tuple[BulletSet, list[mapping.Row]]]) -> Path:
    """fonts/CREDITS.md: the attribution required for each font."""

    lines = [
        "# Credits",
        "",
        "<!-- Generated by `nycbullets build`. Do not edit. -->",
        "",
        "The bullet artwork comes from the Wikimedia Commons category",
        "[New York City Subway bullets]"
        "(https://commons.wikimedia.org/wiki/Category:New_York_City_Subway_bullets).",
        "Nearly all of it is the work of the Metropolitan Transportation",
        "Authority and is in the public domain. The bullets below are under",
        "licenses that require attribution.",
        "",
        "| Bullet | Author | License | Fonts |",
        "|--------|--------|---------|-------|",
    ]
    by_file: dict[str, list[str]] = {}
    for bset, rows in fonts:
        for c in credits_for({r.file for r in rows}):
            by_file.setdefault(c.file, []).append(bset.font_file.name)
    for c in credits_for(set(by_file)):
        lines.append(f"| [{c.title}]({c.page}) | {c.artist} | {c.license} | "
                     f"{', '.join(by_file[c.file])} |")
    path = FONT_DIR / "CREDITS.md"
    path.write_text("\n".join(lines) + "\n")
    return path


def build_font(bset: BulletSet, rows: list[mapping.Row],
               bullets: dict[str, svgnorm.Bullet]) -> Path:
    rows = sorted(rows, key=lambda r: r.codepoint)
    keys = {r.key: r for r in rows}

    # --- glyph order: .notdef, space, bullets, layers, component chars ---
    order = [".notdef", "space"]
    bullet_names = {r.key: glyph_name(r.key) for r in rows}
    order += [bullet_names[r.key] for r in rows]

    cmap = {0x20: "space"}
    for r in rows:
        cmap[r.codepoint] = bullet_names[r.key]

    # Characters typed as part of keys.
    chars = sorted({ch for r in rows for ch in r.key})
    char_names = {}
    for ch in chars:
        if ch in keys:
            char_names[ch] = bullet_names[ch]
        else:
            char_names[ch] = char_glyph_name(ch)
            order.append(char_names[ch])
        cmap[ord(ch)] = char_names[ch]

    glyphs = {".notdef": tt_glyph(unknown_box()), "space": tt_glyph(None)}
    advances = {".notdef": UNKNOWN_WIDTH, "space": SPACE_WIDTH}
    for ch, name in char_names.items():
        if name not in glyphs and ch not in keys:
            glyphs[name] = tt_glyph(unknown_box())
            advances[name] = UNKNOWN_WIDTH

    # --- bullets and their color layers ---
    palette: list[tuple[float, float, float, float]] = []
    color_layers: dict[str, list[tuple[str, int]]] = {}
    layer_names = []

    for r in rows:
        bullet = bullets[r.file]
        name = bullet_names[r.key]
        glyphs[name] = tt_glyph(svgnorm.monochrome(bullet))
        advances[name] = bullet.advance

        layers = []
        for i, layer in enumerate(bullet.layers):
            lname = f"{name}.layer{i}"
            glyphs[lname] = tt_glyph(layer.path)
            advances[lname] = bullet.advance
            layer_names.append(lname)
            rgba = tuple(c / 255 for c in layer.color)
            if rgba not in palette:
                palette.append(rgba)
            layers.append((lname, palette.index(rgba)))
        color_layers[name] = layers

    order += layer_names

    fb = FontBuilder(svgnorm.UPM, isTTF=True)
    fb.font.recalcTimestamp = False
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyphs)

    glyf = fb.font["glyf"]
    metrics = {}
    ymin, ymax = 0, 0
    for name in order:
        g = glyf[name]
        g.recalcBounds(glyf)
        lsb = getattr(g, "xMin", 0) if g.numberOfContours else 0
        metrics[name] = (advances[name], lsb)
        if g.numberOfContours:
            ymin, ymax = min(ymin, g.yMin), max(ymax, g.yMax)
    fb.setupHorizontalMetrics(metrics)

    ascent = max(800, ymax)
    descent = min(-200, ymin)
    fb.setupHorizontalHeader(ascent=ascent, descent=descent)

    fb.setupNameTable({
        "familyName": bset.family,
        "styleName": "Regular",
        "uniqueFontIdentifier": f"{VERSION};{VENDOR};{bset.ps_name}",
        "fullName": f"{bset.family} Regular",
        "version": f"Version {VERSION}",
        "psName": bset.ps_name,
        "copyright": copyright_notice(rows),
        "description": "New York City Subway route bullets as an OpenType "
                       "color font (COLR and SVG). Type a route key such as "
                       "F, Fd or M.brown, or use the Private Use Area code "
                       "points.",
        "licenseDescription": license_notice(rows),
    })

    pua = [r.codepoint for r in rows]
    fb.setupOS2(
        achVendID=VENDOR,
        usWeightClass=400,
        fsSelection=0x40,
        sTypoAscender=ascent,
        sTypoDescender=descent,
        sTypoLineGap=0,
        usWinAscent=ascent,
        usWinDescent=-descent,
        sxHeight=500,
        sCapHeight=700,
        usFirstCharIndex=0x20,
        usLastCharIndex=max(pua),
        ulUnicodeRange2=1 << (60 - 32),   # bit 60: Private Use Area
    )
    fb.setupPost()
    fb.font["head"].created = TIMESTAMP
    fb.font["head"].modified = TIMESTAMP

    # --- GSUB: multi-character keys as ligatures ---
    ligatures = []
    for r in sorted(rows, key=lambda r: (-len(r.key), r.key)):
        if len(r.key) > 1:
            components = " ".join(char_names[ch] for ch in r.key)
            ligatures.append(f"    sub {components} by {bullet_names[r.key]};")
    fea = "\n".join([
        "languagesystem DFLT dflt;",
        "languagesystem latn dflt;",
        "lookup BULLETS {",
        *ligatures,
        "} BULLETS;",
        *(f"feature {tag} {{ lookup BULLETS; }} {tag};"
          for tag in ("rlig", "liga", "calt")),
    ])
    addOpenTypeFeaturesFromString(fb.font, fea)

    # --- COLR / CPAL ---
    fb.font["COLR"] = buildCOLR(color_layers, version=0)
    fb.font["CPAL"] = buildCPAL([palette])

    # --- SVG ---
    svg = newTable("SVG ")
    svg.docList = []
    gids = {name: i for i, name in enumerate(order)}
    for r in rows:
        gid = gids[bullet_names[r.key]]
        svg.docList.append(
            SVGDocument(svg_document(gid, bullets[r.file]), gid, gid, False)
        )
    fb.font["SVG "] = svg

    FONT_DIR.mkdir(parents=True, exist_ok=True)
    fb.save(bset.font_file)
    return bset.font_file


def run() -> None:
    sets, all_set = load_config()
    tables = check_tables([*sets, all_set])

    files = sorted({r.file for rows in tables.values() for r in rows})
    sources = {f: svgnorm.load_source(SOURCE_DIR / f) for f in files}
    scales = svgnorm.scales(sources)
    bullets = {f: svgnorm.to_bullet(sources[f], scales[f]) for f in files}

    for bset in [*sets, all_set]:
        path = build_font(bset, tables[bset.id], bullets)
        print(f"{path.relative_to(FONT_DIR.parent)}: "
              f"{len(tables[bset.id])} bullets")

    path = write_credits([(b, tables[b.id]) for b in [*sets, all_set]])
    print(f"{path.relative_to(FONT_DIR.parent)}")
