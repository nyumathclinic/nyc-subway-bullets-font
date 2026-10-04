import pytest

from nycbullets import mapping
from nycbullets.config import load_config

GUESSES = [
    ("NYCS-bull-trans-F-Std.svg", ("F", "std")),
    ("NYCS-bull-trans-Fd-Std.svg", ("Fd", "std")),
    ("NYCS-bull-trans---Std.svg", ("-", "std")),
    ("NYCS-bull-trans--d-Std.svg", ("-d", "std")),
    ("NYCS-bull-trans-SIRd-Std.svg", ("SIRd", "std")),
    ("NYCS-bull-trans-M-Std-brown.svg", ("M.brown", "std")),
    ("NYCS-bull-trans-Bsd-Std.svg", ("Bsd", "std")),
    ("NYCS-bull-trans-10-Std.svg", ("10", "std")),
    ("NYCS-bull-trans-A gray.svg", ("A.gray", "helv")),
    ("NYCS-bull-trans-Ad-(1979-1987).svg", ("Ad.1979-1987", "helv")),
    ("NYCS-bull-trans-JFK.svg", ("JFK", "helv")),
    ("NYCTA-Standard-Medium-Md nassau.svg", ("Md.nassau", "nycta")),
    ("NYCTA Standard-Medium-Qd.svg", ("Qd", "nycta")),
    ("AA Train (1967-1979).svg", ("AA.1967-1979", "retired")),
    ("SS Train (1967-1968, Yellow).svg", ("SS.1967-1968.yellow", "retired")),
    ("RR Train - Yellow diamond.svg", ("RRd.yellow", "retired")),
    ("3 (1967-1979 New York City Subway bullet).svg", ("3.1967-1979", "retired")),
    ("Bullet QB Red TEST.svg", None),
]


@pytest.mark.parametrize("filename,expected", GUESSES)
def test_guess(filename, expected):
    assert mapping.guess(filename) == expected


def test_tag_key():
    assert mapping.tag_key("F", "helv") == "F.helv"
    assert mapping.tag_key("B.broadway", "nycta") == "B.nycta.broadway"


def all_sets():
    sets, all_set = load_config()
    return [*sets, all_set]


@pytest.mark.parametrize("bset", all_sets(), ids=lambda s: s.id)
def test_table_is_clean(bset):
    rows = mapping.read_table(bset.mapping_file)
    if not rows:
        pytest.skip(f"{bset.mapping_file} not generated yet")
    assert mapping.problems(rows) == []


def test_diamond_keys_match_shapes():
    """A key has the diamond modifier d exactly when the artwork is one."""

    from nycbullets.config import SOURCE_DIR
    from nycbullets.svgnorm import load_source

    sets, all_set = load_config()
    rows = mapping.read_table(all_set.mapping_file)
    if not rows:
        pytest.skip("mapping tables not generated yet")
    wrong = [
        r.key for r in rows
        if load_source(SOURCE_DIR / r.file).is_diamond
        != mapping.key_is_diamond(r.key)
    ]
    assert wrong == []


def test_sort_key_order():
    keys = ["A", "-", "10", "Ad", "2", "AA.1967-1979", "1d", "A.gray", "1",
            "-d", "B", "Ad.gray"]
    assert sorted(keys, key=mapping.sort_key) == [
        "-", "-d", "1", "1d", "2", "10",
        "A", "A.gray", "Ad", "Ad.gray", "AA.1967-1979", "B",
    ]


@pytest.mark.parametrize("key,expected", [
    ("1", "1"), ("Fd", "F"), ("Bsd", "B"), ("SIRd", "SIR"),
    ("M.brown", "M"), ("QBd.1979-1985", "QB"), ("-d", "blank"),
    ("JFK", "airplane"), ("S6d", "S"), ("SR", "S with small R"),
    ("SR.helv", "S with small R"), ("SR.blue", "S"), ("SFd.silver", "S"),
])
def test_symbol(key, expected):
    assert mapping.symbol(key) == expected


def test_color_name():
    assert mapping.color_name((0xEE, 0x35, 0x2E, 255)) == "red"
    assert mapping.color_name((0xFF, 0x00, 0x00, 255)) == "red"
    assert mapping.color_name((0xA7, 0xA9, 0xAC, 255)) == "light gray"
