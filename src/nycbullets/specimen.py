"""
Write an HTML specimen of every font into specimens/.

Open specimens/index.html in a browser to check the fonts.  Each bullet is
shown twice: once typed as its key (exercising the ligatures) and once by
its Private Use Area code point.

Which color table a browser uses depends on the browser: Safari renders the
SVG table, Chrome the COLR table, Firefox either.

The same pieces build the specimen page of the documentation site (see
mkdocs_hooks.py).
"""

from __future__ import annotations

import html
import os
from collections.abc import Callable

from . import mapping
from .config import SPECIMEN_DIR, BulletSet, load_config

INTRO = "Top: typed as the key (ligature). Bottom: Private Use Area code point."

# The var() colors come from the Material for MkDocs theme; the fallbacks
# apply in the standalone page.
LAYOUT_CSS = """\
.specimen-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(9rem, 1fr));
        gap: .5rem; }
.specimen-cell { border: 1px solid var(--md-default-fg-color--lightest, #eee);
        border-radius: 6px; padding: .5rem; text-align: center; }
.specimen-b { font-size: 3rem; line-height: 1.2; }
.specimen-key { font-family: ui-monospace, monospace; font-size: .9rem; }
.specimen-desc { font-size: .7rem; color: var(--md-default-fg-color--light, #666);
        line-height: 1.3; }
.specimen-cp { font-size: .7rem; color: var(--md-default-fg-color--lighter, #999); }
"""

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
{css}
body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #222; }}
h2 {{ margin-top: 2.5rem; border-bottom: 1px solid #ccc; }}
</style>
</head>
<body>
<h1>{title}</h1>
<p>{intro}</p>
{sections}
</body>
</html>
"""


def all_sets() -> list[BulletSet]:
    sets, all_set = load_config()
    return [*sets, all_set]


def font_faces(url: Callable[[BulletSet], str]) -> str:
    """An @font-face rule and an .f-<id> class for every font.  `url`
    gives the URL of a set's font file."""

    return "\n".join(
        f'@font-face {{ font-family: "bullets-{b.id}"; src: url("{url(b)}"); }}\n'
        f'.f-{b.id} {{ font-family: "bullets-{b.id}"; }}'
        for b in all_sets()
    )


def grid(bset: BulletSet) -> str:
    """One set's bullets as a single-line <div>."""

    cells = []
    for r in sorted(mapping.read_table(bset.mapping_file),
                    key=lambda r: r.codepoint):
        cells.append(
            '<div class="specimen-cell">'
            f'<div class="specimen-b f-{bset.id}">{html.escape(r.key)}</div>'
            f'<div class="specimen-b f-{bset.id}">&#x{r.codepoint:04X};</div>'
            f'<div class="specimen-key">{html.escape(r.key)}</div>'
            f'<div class="specimen-cp">U+{r.codepoint:04X}</div>'
            f'<div class="specimen-desc">{html.escape(r.description)}</div>'
            f'<div class="specimen-desc">{html.escape(r.service)}</div>'
            '</div>'
        )
    return f'<div class="specimen-grid">{"".join(cells)}</div>'


def markdown() -> str:
    """The specimen as a Markdown page for the documentation site."""

    parts = [
        "# Specimen\n",
        f"{INTRO} Safari draws the SVG color table, Chrome the COLR table, "
        "and Firefox either.\n",
    ]
    for bset in all_sets():
        parts.append(f"## {bset.family}\n\n{grid(bset)}\n")
    return "\n".join(parts)


def run() -> None:
    SPECIMEN_DIR.mkdir(parents=True, exist_ok=True)
    faces = font_faces(lambda b: os.path.relpath(b.font_file, SPECIMEN_DIR))
    sections = "\n".join(
        f'<h2>{html.escape(b.family)}</h2>\n{grid(b)}' for b in all_sets()
    )
    out = SPECIMEN_DIR / "index.html"
    out.write_text(PAGE.format(
        title="NYC Subway Bullets specimen",
        css=faces + "\n" + LAYOUT_CSS,
        intro=INTRO,
        sections=sections,
    ))
    print(f"{out}")
