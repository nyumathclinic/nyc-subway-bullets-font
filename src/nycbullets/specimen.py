"""
Write an HTML specimen of every font into specimens/.

Open specimens/index.html in a browser to check the fonts.  Each bullet is
shown twice: once typed as its key (exercising the ligatures) and once by
its Private Use Area code point.

Which color table a browser uses depends on the browser: Safari renders the
SVG table, Chrome the COLR table, Firefox either.
"""

from __future__ import annotations

import html
import os

from . import mapping
from .config import SPECIMEN_DIR, load_config

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
{faces}
body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #222; }}
h2 {{ margin-top: 2.5rem; border-bottom: 1px solid #ccc; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(9rem, 1fr));
        gap: .5rem; }}
.cell {{ border: 1px solid #eee; border-radius: 6px; padding: .5rem;
        text-align: center; }}
.b {{ font-size: 3rem; line-height: 1.2; }}
.key {{ font-family: ui-monospace, monospace; font-size: .9rem; }}
.desc {{ font-size: .7rem; color: #666; }}
.cp {{ font-size: .7rem; color: #999; }}
</style>
</head>
<body>
<h1>{title}</h1>
<p>Top: typed as the key (ligature). Bottom: Private Use Area code point.</p>
{sections}
</body>
</html>
"""


def run() -> None:
    sets, all_set = load_config()
    SPECIMEN_DIR.mkdir(parents=True, exist_ok=True)

    faces = []
    sections = []
    for bset in [*sets, all_set]:
        rel = os.path.relpath(bset.font_file, SPECIMEN_DIR)
        family = f"bullets-{bset.id}"
        faces.append(
            f'@font-face {{ font-family: "{family}"; src: url("{rel}"); }}\n'
            f'.f-{bset.id} {{ font-family: "{family}"; }}'
        )
        cells = []
        for r in sorted(mapping.read_table(bset.mapping_file),
                        key=lambda r: r.codepoint):
            cells.append(
                '<div class="cell">'
                f'<div class="b f-{bset.id}">{html.escape(r.key)}</div>'
                f'<div class="b f-{bset.id}">&#x{r.codepoint:04X};</div>'
                f'<div class="key">{html.escape(r.key)}</div>'
                f'<div class="cp">U+{r.codepoint:04X}</div>'
                f'<div class="desc">{html.escape(r.description)}</div>'
                '</div>'
            )
        sections.append(
            f'<h2>{html.escape(bset.family)}</h2>\n'
            f'<div class="grid">{"".join(cells)}</div>'
        )

    out = SPECIMEN_DIR / "index.html"
    out.write_text(PAGE.format(
        title="NYC Subway Bullets specimen",
        faces="\n".join(faces),
        sections="\n".join(sections),
    ))
    print(f"{out}")
