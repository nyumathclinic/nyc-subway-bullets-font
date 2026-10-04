"""
MkDocs hooks for the documentation site (see mkdocs.yml).

They add files that live outside docs/ or are generated:

- fonts/*.ttf, so the site can serve them for download and for the specimen;
- credits.md, from fonts/CREDITS.md;
- specimen.md, the specimen page;
- stylesheets/bullets.css, an @font-face rule and an .f-<id> class for every
  font (so any page can show bullets) plus the specimen layout.
"""

from __future__ import annotations

from mkdocs.structure.files import File, Files

from nycbullets import specimen
from nycbullets.config import FONT_DIR, ROOT


def on_files(files: Files, config) -> Files:
    for bset in specimen.all_sets():
        files.append(File(
            bset.font_file.relative_to(ROOT).as_posix(),
            src_dir=str(ROOT),
            dest_dir=config["site_dir"],
            use_directory_urls=config["use_directory_urls"],
        ))
    files.append(File.generated(
        config, "credits.md", content=(FONT_DIR / "CREDITS.md").read_text()))
    files.append(File.generated(
        config, "specimen.md", content=specimen.markdown()))
    # url() in a stylesheet is relative to the stylesheet.
    css = specimen.font_faces(lambda b: f"../fonts/{b.font_file.name}")
    files.append(File.generated(
        config, "stylesheets/bullets.css",
        content=css + "\n" + specimen.LAYOUT_CSS))
    return files
