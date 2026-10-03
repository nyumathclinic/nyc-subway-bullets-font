"""Check the built fonts: tables present, every key and code point works."""

import pytest
import uharfbuzz as hb
from fontTools.ttLib import TTFont

from nycbullets import mapping
from nycbullets.config import load_config
from nycbullets.fontbuild import glyph_name


def all_sets():
    sets, all_set = load_config()
    return [*sets, all_set]


@pytest.fixture(params=all_sets(), ids=lambda s: s.id)
def built(request):
    bset = request.param
    if not bset.font_file.exists():
        pytest.skip(f"{bset.font_file} not built yet")
    rows = mapping.read_table(bset.mapping_file)
    font = TTFont(bset.font_file)
    face = hb.Face(hb.Blob.from_file_path(str(bset.font_file)))
    return bset, rows, font, hb.Font(face)


def shape(hbfont, text):
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(hbfont, buf, {})
    return buf.glyph_infos


def test_tables(built):
    _, rows, font, _ = built
    for tag in ("glyf", "COLR", "CPAL", "SVG ", "cmap"):
        assert tag in font
    # Ligatures are only needed for keys longer than one character.
    if any(len(r.key) > 1 for r in rows):
        assert "GSUB" in font
    assert len(font["SVG "].docList) == len(rows)
    assert len(font["COLR"].ColorLayers) == len(rows)


def test_every_key_shapes_to_its_bullet(built):
    _, rows, font, hbfont = built
    order = font.getGlyphOrder()
    for r in rows:
        glyphs = [order[g.codepoint] for g in shape(hbfont, r.key)]
        assert glyphs == [glyph_name(r.key)], r.key


def test_every_codepoint_maps_to_its_bullet(built):
    _, rows, font, _ = built
    cmap = font.getBestCmap()
    for r in rows:
        assert cmap[r.codepoint] == glyph_name(r.key)


def test_keys_separated_by_spaces(built):
    _, rows, font, hbfont = built
    order = font.getGlyphOrder()
    keys = [r.key for r in rows[:5]]
    glyphs = [order[g.codepoint] for g in shape(hbfont, " ".join(keys))]
    assert [g for g in glyphs if g != "space"] == [glyph_name(k) for k in keys]
