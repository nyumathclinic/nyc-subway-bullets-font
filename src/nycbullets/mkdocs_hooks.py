"""
MkDocs hooks for the documentation site (see mkdocs.yml).

They add files that live outside docs/ or are generated:

- fonts/*.ttf, so the site can serve them for download and for the specimen;
- fonts/NYCSubwayBullets.zip, all the fonts with their credits and licenses;
- credits.md, from fonts/CREDITS.md;
- specimen.md, the specimen page;
- stylesheets/bullets.css, an @font-face rule and an .f-<id> class for every
  font (so any page can show bullets) plus the specimen layout.
"""

from __future__ import annotations

import io
import zipfile

from mkdocs.structure.files import File, Files

from nycbullets import specimen
from nycbullets.config import FONT_DIR, ROOT

ZIP_NAME = "NYCSubwayBullets"


def fonts_zip() -> bytes:
    """The fonts, CREDITS.md and the licenses that apply to them, in a
    NYCSubwayBullets/ folder.  The timestamps are fixed so that the same
    fonts give the same archive."""

    members = [b.font_file for b in specimen.all_sets()]
    members += [FONT_DIR / "CREDITS.md",
                ROOT / "LICENSES" / "CC0-1.0.txt",
                ROOT / "LICENSES" / "CC-BY-4.0.txt"]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in members:
            info = zipfile.ZipInfo(f"{ZIP_NAME}/{path.name}",
                                   date_time=(2026, 1, 1, 0, 0, 0))
            info.external_attr = 0o644 << 16
            zf.writestr(info, path.read_bytes(), zipfile.ZIP_DEFLATED)
    return buf.getvalue()


def on_files(files: Files, config) -> Files:
    for bset in specimen.all_sets():
        files.append(File(
            bset.font_file.relative_to(ROOT).as_posix(),
            src_dir=str(ROOT),
            dest_dir=config["site_dir"],
            use_directory_urls=config["use_directory_urls"],
        ))
    files.append(File.generated(
        config, f"fonts/{ZIP_NAME}.zip", content=fonts_zip()))
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
