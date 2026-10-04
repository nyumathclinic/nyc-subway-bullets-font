"""
Assign each bullet file a typed key and a Private Use Area codepoint.

The result lives in data/mappings/<set>.tsv, one row per file:

    file        the file name in sources/commons/
    key         what you type to get the bullet: F, Fd, M.brown, SIRd, ...
    codepoint   the bullet's PUA code point, e.g. E00A
    description what the bullet looks like: the symbol on it, then the
                color and shape of the background, e.g. "1 red circle" or
                "B yellow diamond" (generated from the artwork)
    service     the service the bullet stands for, e.g. "Broadway–Seventh
                Avenue Local" (filled in by hand; used in the documentation)

Keys have the form  <base><mods>[.<variant>...]  where

    base     the route designation: a digit string, an upper-case string
             such as F, SIR, JFK or S6, or "-" for the dash bullet
    mods     optional lower-case modifiers: "d" for the diamond (express)
             form, "s" for the R32 "special" form (Bs, Bsd, Ds, Dsd)
    variant  lower-case words distinguishing alternate versions: colors
             (M.brown), historical routings (B.broadway), years
             (A.1967-1979), style (4d.std, 4d.helv), ...

The tables are meant to be reviewed and edited by hand.  Running this step
again only appends rows for new files: existing rows, including edited keys
and assigned codepoints, are kept as they are, so codepoints are stable.
New rows get code points in key order (see sort_key) after the existing
ones.  `nycbullets map --renumber` reassigns all code points in key order;
since that changes code points documents may use, do it only before
publishing.
Files whose key cannot be guessed, or whose key collides with another, get
the key TODO; the build step refuses to run until those are fixed.

data/mappings/all.tsv is derived from the per-set tables: each distinct file
appears once, under the first set (in config order) that contains it, and
its key gets that set's id as a tag after the base, e.g. F.helv or
B.nycta.broadway.  Bullets whose home set is the first set keep their key
unchanged.  Only the codepoints in all.tsv are preserved between runs.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from dataclasses import dataclass, replace
from pathlib import Path

from . import svgnorm
from .config import (MANIFEST, MAPPING_DIR, SOURCE_DIR, BulletSet,
                     allowed_licenses, load_config)

PUA_START = 0xE000
TODO = "TODO"

FIELDS = ["file", "key", "codepoint", "description", "service"]

KEY_RE = re.compile(r"^(-|[0-9]+|[A-Z][A-Z0-9]*|Special)(s?d?)((?:\.[a-z0-9-]+)*)$")


@dataclass
class Row:
    file: str
    key: str
    codepoint: int
    description: str
    service: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "file": self.file,
            "key": self.key,
            "codepoint": f"{self.codepoint:04X}",
            "description": self.description,
            "service": self.service,
        }


# ---------------------------------------------------------------------------
# Guessing a key from a file name
# ---------------------------------------------------------------------------

BASE_RE = re.compile(r"^(?P<base>-|[0-9]+|[A-Z][A-Z0-9]*)(?P<mods>s?d?)(?P<rest>.*)$")
YEARS_RE = re.compile(r"\(?((?:pre-)?\d{4}(?:-\d{4})?)\)?")


def _variant_tokens(rest: str) -> list[str]:
    """Split the trailing part of a file name into lower-case variant words."""

    years = YEARS_RE.findall(rest)
    rest = YEARS_RE.sub(" ", rest)
    rest = rest.replace("New York City Subway bullet", " ")
    words = [w.lower() for w in re.split(r"[-\s,()]+", rest) if w]
    return years + words


def guess(filename: str) -> tuple[str, str] | None:
    """
    Guess (key, style) from a Commons file name, or None if we can't.

    style is one of std, helv, nycta, retired; it is used to disambiguate
    files that would otherwise get the same key in one set.
    """

    stem = Path(filename).stem

    if m := re.match(r"^NYCS-bull-trans-(.*)$", stem):
        body, style = m.group(1), "helv"
    elif m := re.match(r"^NYCTA[- ]Standard-Medium-(.*)$", stem):
        body, style = m.group(1), "nycta"
    elif m := re.match(r"^(?P<base>[A-Z0-9]+|Special)(?: Train)?(?P<rest>[ (].*)$", stem):
        body, style = m.group("base") + m.group("rest"), "retired"
    else:
        return None

    m = BASE_RE.match(body)
    if not m:
        return None

    base, mods, rest = m.group("base"), m.group("mods"), m.group("rest")
    if body.startswith("Special"):
        base, mods, rest = "Special", "", body[len("Special"):]

    words = _variant_tokens(rest)

    if "std" in words:
        style = "std"
        words.remove("std")
    if "diamond" in words:
        words.remove("diamond")
        mods += "d"

    key = base + mods + "".join("." + w for w in words)
    if not KEY_RE.match(key):
        return None
    return key, style


# ---------------------------------------------------------------------------
# Descriptions
# ---------------------------------------------------------------------------

# Names for the background colors in the artwork.  A color not listed
# gets the name of the nearest one that is.
COLOR_NAMES = {
    "red": ["#EE352E", "#E60D2E", "#E00034", "#E30F00"],
    "orange": ["#FF6319", "#F56600"],
    "yellow": ["#FCCC0A", "#F7D117", "#F0AB00"],
    "lime green": ["#6CBE45", "#7DBA00"],
    "green": ["#00933C", "#009645", "#00AF3F"],
    "turquoise": ["#00ADD0", "#1E9DBF", "#00A3E0"],
    "blue": ["#0039A6", "#2850AD", "#0033AB", "#0065BD", "#0078C6"],
    "dark blue": ["#002856", "#0F2B51"],
    "purple": ["#B933AD", "#BA1FB5"],
    "magenta": ["#DA39AF"],
    "brown": ["#996633", "#965700"],
    "light gray": ["#A7A9AC"],
    "dark gray": ["#808183", "#808080", "#4D4D4D"],
    "black": ["#000000", "#2A2623"],
    "white": ["#FFFFFF"],
}


def color_name(color: svgnorm.Color) -> str:
    def distance(hex_color: str) -> int:
        rgb = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
        return sum((a - b) ** 2 for a, b in zip(color, rgb))

    return min(((distance(h), name) for name, hexes in COLOR_NAMES.items()
                for h in hexes))[1]


# Bullets that don't show their route designation.
SYMBOLS = {
    "-": "blank",
    "JFK": "airplane",
    "Special": "S",
    "S6": "S",
    "SB": "S",
    "SF": "S with small F",
    "SR": "S with small R",
}

# ... and variants of those that show a plain S.
PLAIN_S = {("SF", "silver"), ("SR", "blue")}


def symbol(key: str) -> str:
    """What is printed on the bullet with this key."""

    m = KEY_RE.match(key)
    if not m:
        return key
    base, variants = m.group(1), m.group(3).split(".")
    if any((base, v) in PLAIN_S for v in variants):
        return "S"
    return SYMBOLS.get(base, base)


def describe(filename: str, key: str) -> str:
    """What the bullet looks like: "1 red circle", "B yellow diamond"."""

    src = svgnorm.load_source(SOURCE_DIR / filename)
    shape = "diamond" if src.is_diamond else "circle"
    sym = symbol(key)
    sep = ", " if " " in sym else " "    # "S with small R, dark gray circle"
    return f"{sym}{sep}{color_name(src.background)} {shape}"


# ---------------------------------------------------------------------------
# Reading and writing tables
# ---------------------------------------------------------------------------

def read_table(path: Path) -> list[Row]:
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return [
            Row(r["file"], r["key"], int(r["codepoint"], 16), r["description"],
                r.get("service", ""))
            for r in csv.DictReader(f, delimiter="\t")
        ]


def write_table(path: Path, rows: list[Row]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(rows, key=lambda r: r.codepoint)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, FIELDS, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row.as_dict())


def problems(rows: list[Row]) -> list[str]:
    """Return a list of complaints about a table (TODO keys, duplicates...)."""

    msgs = []
    seen: dict[str, str] = {}
    cps: dict[int, str] = {}
    for row in rows:
        if row.key == TODO:
            msgs.append(f"{row.file}: key is TODO")
            continue
        if not KEY_RE.match(row.key):
            msgs.append(f"{row.file}: malformed key {row.key!r}")
        if row.key in seen:
            msgs.append(f"{row.file}: key {row.key!r} also used by {seen[row.key]}")
        seen[row.key] = row.file
        if row.codepoint in cps:
            msgs.append(f"{row.file}: codepoint {row.codepoint:04X} also "
                        f"used by {cps[row.codepoint]}")
        cps[row.codepoint] = row.file
    return msgs


# ---------------------------------------------------------------------------
# Updating tables
# ---------------------------------------------------------------------------

def sort_key(key: str):
    """
    Order keys by route, then modifiers, then variants: the dash bullet,
    numbered routes in numeric order, then lettered routes alphabetically,
    so that 1, 1d, 2, ..., 13, A, A.gray, Ad, AA, B, ...  TODO goes last.
    """

    base_mods, *variants = key.split(".")
    m = re.match(r"^(-|[0-9]+|[A-Z][A-Z0-9]*|Special)(s?d?)$", base_mods)
    if not m:
        return ((3, 0, key), "", variants)
    base, mods = m.groups()
    if base == "-":
        route = (0, 0, "")
    elif base.isdigit():
        route = (1, int(base), "")
    else:
        route = (2, 0, base)
    return (route, mods, variants)


def renumber(rows: list[Row]) -> list[Row]:
    """Reassign code points from PUA_START in key order."""

    rows = sorted(rows, key=lambda r: sort_key(r.key))
    return [replace(r, codepoint=PUA_START + i) for i, r in enumerate(rows)]


def update_set(bset: BulletSet, files: list[str]) -> list[Row]:
    """Append rows for new files to a set's table; return all rows."""

    old = read_table(bset.mapping_file)
    keep = [r for r in old if r.file in files]
    for r in old:
        if r.file not in files:
            print(f"  {bset.id}: dropping {r.file} (no longer in the set)")

    known = {r.file for r in keep}
    new_files = [f for f in files if f not in known]
    if not new_files:
        return keep

    used = {r.key for r in keep}
    next_cp = max([r.codepoint + 1 for r in old], default=PUA_START)

    guesses = {f: guess(f) for f in new_files}

    # Keys that more than one new file would get, or that are already used.
    counts: dict[str, int] = {}
    for g in guesses.values():
        if g:
            counts[g[0]] = counts.get(g[0], 0) + 1

    def with_style(key: str, style: str) -> str:
        base, *rest = key.split(".")
        return ".".join([base, *rest, style])

    rows = list(keep)
    new_rows: list[Row] = []
    for f in new_files:
        g = guesses[f]
        if g is None:
            key = TODO
            print(f"  {bset.id}: cannot guess a key for {f}", file=sys.stderr)
        else:
            key, style = g
            if counts[key] > 1 or key in used:
                key = with_style(key, style)
            if key in used:
                print(f"  {bset.id}: {f} collides on {key}", file=sys.stderr)
                key = TODO
        if key != TODO:
            used.add(key)
        new_rows.append(Row(f, key, 0, describe(f, key)))

    for r in sorted(new_rows, key=lambda r: sort_key(r.key)):
        r.codepoint = next_cp
        next_cp += 1
    rows += new_rows

    print(f"  {bset.id}: {len(new_files)} new row(s)")
    return rows


def key_is_diamond(key: str) -> bool:
    """Whether a key names a diamond bullet (Fd, SIRd, QBd.1979-1985)."""

    return key.split(".")[0].endswith("d")


def tag_key(key: str, tag: str) -> str:
    """Insert a set tag after the base: B.broadway + nycta -> B.nycta.broadway."""

    base, *rest = key.split(".")
    return ".".join([base, tag, *rest])


def derive_all(sets: list[BulletSet], all_set: BulletSet,
               tables: dict[str, list[Row]]) -> list[Row]:
    """Build the All table: each file once, under its home set."""

    old = {r.file: r.codepoint for r in read_table(all_set.mapping_file)}
    next_cp = max(old.values(), default=PUA_START - 1) + 1

    rows: list[Row] = []
    placed: set[str] = set()
    for i, bset in enumerate(sets):
        for r in tables[bset.id]:
            if r.file in placed:
                continue
            placed.add(r.file)
            key = r.key if (i == 0 or r.key == TODO) else tag_key(r.key, bset.id)
            rows.append(replace(r, key=key, codepoint=old.get(r.file, 0)))

    for r in sorted((r for r in rows if r.file not in old),
                    key=lambda r: sort_key(r.key)):
        r.codepoint = next_cp
        next_cp += 1
    return rows


def set_files(bset: BulletSet, manifest: dict) -> list[str]:
    """The files of a set whose license is allowed (config/sets.toml)."""

    allowed = allowed_licenses()
    files = []
    for name, meta in manifest["files"].items():
        if bset.id not in meta["sets"]:
            continue
        if meta["license"] not in allowed:
            print(f"  {bset.id}: skipping {name} (license: {meta['license']})")
            continue
        files.append(name)
    return sorted(files, key=str.casefold)


def run(renumber_all: bool = False) -> None:
    """
    Update the mapping tables.  With renumber_all, also reassign every code
    point in key order -- this changes code points that documents may
    already use, so do it only before publishing the fonts.
    """

    sets, all_set = load_config()
    manifest = json.loads(MANIFEST.read_text())

    missing = [f for f in manifest["files"] if not (SOURCE_DIR / f).exists()]
    if missing:
        raise SystemExit(f"{len(missing)} file(s) in the manifest have not "
                         f"been downloaded yet; run `nycbullets download`.")

    tables = {}
    for bset in sets:
        rows = update_set(bset, set_files(bset, manifest))
        if renumber_all:
            rows = renumber(rows)
        write_table(bset.mapping_file, rows)
        tables[bset.id] = rows

    all_rows = derive_all(sets, all_set, tables)
    if renumber_all:
        all_rows = renumber(all_rows)
    write_table(all_set.mapping_file, all_rows)

    bad = False
    for bset in [*sets, all_set]:
        rows = read_table(bset.mapping_file)
        msgs = problems(rows)
        print(f"{bset.mapping_file.relative_to(MAPPING_DIR.parent.parent)}: "
              f"{len(rows)} bullets" + (f", {len(msgs)} problem(s)" if msgs else ""))
        for msg in msgs:
            print(f"    {msg}")
        bad = bad or bool(msgs)

    if bad:
        print("\nEdit the tables above to fix the problems, then rerun.")
