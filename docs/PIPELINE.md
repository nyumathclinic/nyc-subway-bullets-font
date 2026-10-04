# How the fonts are built

Everything is driven by `make` (which calls `uv run nycbullets <step>`).
Each step reads only files written by earlier steps, so you can rerun any
step on its own.

```
Commons ──download──▶ sources/commons/*.svg, sources/manifest.json
        ──mappings──▶ data/mappings/<set>.tsv        (review & edit these)
        ──fonts─────▶ fonts/NYCSubwayBullets-<Set>.ttf
        ──specimens─▶ specimens/index.html
        ──latex─────▶ latex/*.def, latex/nycbullets-keytable-*.tex, latex/*.ttf
        ──doc───────▶ latex/nycbullets.pdf (l3build), copied to docs/
```

Requirements: [uv](https://docs.astral.sh/uv/) (it installs the Python
dependencies listed in `pyproject.toml` on first use) and a TeX Live with
`l3build` and LuaLaTeX.

## 1. Download — `make download`

Source: `src/nycbullets/commons.py`. Configuration: `config/sets.toml`.

Each set in `config/sets.toml` lists one or more Commons categories. The
downloader lists the SVG files in each category (and recursively in its
subcategories when `recurse = true`, which is used for *Retired*). It then
asks the Commons API for each file's URL, SHA-1 and license, and downloads
each file once into `sources/commons/`. A file can belong to several sets.
For example, the Standard-set files also appear in R62A, R32 and Retired.

`sources/manifest.json` records every file's Commons title, URL, SHA-1,
license, author and sets.

Rerunning is cheap. A file is downloaded only if it is missing or its SHA-1
differs from the one Commons reports, which means it was updated upstream.
The downloader:

- identifies itself with a User-Agent;
- waits 1–4 s between downloads;
- honors `429 Too Many Requests`, including `Retry-After`, which can be as
  long as 10 minutes.

Commons throttles media downloads hard. Expect bursts of a few files
followed by a 10-minute `Retry-After` pause, so a download from scratch can
take hours. Two environment variables help:

- `NYCBULLETS_CONTACT` sets the contact information, such as an email
  address or a URL, in the User-Agent; it defaults to the maintainer's
  address. Wikimedia's
  [User-Agent policy](https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy)
  asks for this.
- `NYCBULLETS_DELAY="min,max"` sets the random pause between downloads in
  seconds. The default is `10,20`.

```sh
NYCBULLETS_CONTACT="you@example.com" make download
```

The manifest is written before any file is downloaded. An interrupted run
can simply be restarted: it picks up where it stopped. `make mappings`
refuses to run until every file in the manifest has been downloaded.

PNG files in the categories are ignored. A cached file that is no longer in
any category is reported, but not deleted.

## 2. Key mapping — `make mappings`

Source: `src/nycbullets/mapping.py`.

Every bullet gets a **key**, which is what you type, and a **Private Use
Area code point**. These live in `data/mappings/<set>.tsv`, one table per
set, which is the place to review and fix things:

| column      | meaning                                                        |
|-------------|----------------------------------------------------------------|
| file        | file name in `sources/commons/`                                |
| key         | e.g. `F`, `Fd`, `SIRd`, `M.brown`, `AA.1967-1979`              |
| codepoint   | hex, e.g. `E00F`                                               |
| description | what it looks like, e.g. `1 red circle`, from the artwork      |
| service     | e.g. `Broadway–Seventh Avenue Local`; empty for new files, so fill it in by hand |

The description and service appear in the documentation's key tables
(and the HTML specimen), not in the fonts.

**Licenses.** `allowed_licenses` in `config/sets.toml` lists the licenses
that are acceptable in the fonts. It is currently public domain, CC0 and
CC BY 4.0. Files under any other license are skipped and reported. For
example, `Bullet QB Red TEST.svg` in the Legacy set is CC BY-SA 4.0, which
would put the whole font under share-alike, so it is skipped. Bullets under
attribution licenses (CC BY) are credited automatically in three places:

- the fonts' `name` table (copyright and license fields);
- `fonts/CREDITS.md`;
- the Credits section of the LaTeX documentation.

The author and license of each file come from Commons, via
`sources/manifest.json`.

Key syntax: `<route><modifiers>[.<variant>...]`

- **route**: digits (`7`, `10`), capitals (`F`, `SIR`, `JFK`, `S6`), or `-`
  (the dash bullet).
- **modifiers**: `d` for the diamond (express) form; `s` for the R32
  "special" forms (`Bs`, `Bsd`).
- **variants**: lower-case words after dots, for colors (`M.brown`),
  historical routings (`B.broadway`), years (`A.1967-1979`) or style
  (`4d.std`, `4d.helv`).

The first run guesses keys from the file names, for example
`NYCS-bull-trans-Fd-Std.svg` → `Fd` and `RR Train - Yellow diamond.svg` →
`RRd.yellow`. When two files in one set would get the same key, the
drawing style (`.std`, `.helv`, ...) is appended. A file whose key can't be
guessed gets the key `TODO`, and `make fonts` refuses to run until every
`TODO` and every duplicate key is fixed by hand.

Code points follow key order: first the dash bullet, then numbered routes
in numeric order, then lettered routes alphabetically. Each route keeps its
forms together, e.g. `1, 1d, 2, … 13, A, A.gray, Ad, Ad.gray, AA…, B, …`.

Later runs **only append** rows for files that are new in a set. Existing
rows are left exactly as they are, including keys you have edited and the
assigned code points, so code points stay stable. New rows get the next
code points, in key order. Rows for files that have left a set are dropped.

`uv run nycbullets map --renumber` reassigns every code point in key order,
for instance after renaming keys. Because this changes code points that
documents may already use, do it only before publishing a release.

To rename a key, edit the TSV and run `make fonts latex`.

`data/mappings/all.tsv` is derived from the per-set tables, so don't edit
it. It contains each distinct file once, under the first set in
`config/sets.toml` that contains it. Its key gets that set's id as a tag
after the route: `F` (Standard), `F.helv`, `B.nycta.broadway`. Only its
code points are preserved between runs.

## 3. Fonts — `make fonts`

Sources: `src/nycbullets/svgnorm.py` and `src/nycbullets/fontbuild.py`.

**Normalizing the artwork.** First, some SVGs need cleaning up, because
picosvg accepts neither text nor style sheets:

- Empty `<text>` elements, left over in many Inkscape files, are removed.
- A file with real text has its text converted to outlines by Inkscape,
  once. Today that is `NYCS-bull-trans-9-red.svg`, whose "9" is set in
  Arial. The result is kept in `sources/outlined/`, which is committed, so
  rebuilding needs neither Inkscape nor the font. To find Inkscape, the
  build looks at `$INKSCAPE`, then `inkscape` on the `PATH`, then
  `/Applications/Inkscape.app`.
- `fill="currentColor"` is replaced by the inherited `color` value.
- The simple `.class` and element rules of a `<style>` sheet (from
  Illustrator exports) are inlined.

picosvg then reduces each SVG to a flat list of filled paths, converting
circles, polygons, strokes and transforms. Each
path is then scaled into a 1000-unit em, flipped to y-up, and cleaned with
skia-pathops: overlaps are removed and contours turned clockwise.

**Sizing.** Every bullet is scaled by its own height. Diamonds are
recognized by their shape, since not every file name says so: a diamond
fills half its bounding box and a circle 78.5%. A test checks that the
diamond modifier `d` in each key agrees with the shape. Circles and other
non-diamond shapes become 800 units tall. Diamonds become 960 units tall,
the 1.2 ratio of the Standard and Helvetica sets. The source files can't be
trusted to agree: the NYCTA set alone uses seven page sizes, and draws some
diamonds as tall as its circles and others larger. Each bullet is centered
vertically on y = 300, so circles span −100…700. Its advance is its width
plus 50 units on each side. All of these constants are at the top of
`svgnorm.py`.

**Tables in each font.**

- `glyf`: monochrome outlines (the background shape with the lettering cut
  out), for XeLaTeX and other non-color renderers.
- `COLR` v0 / `CPAL`: one flat-color layer glyph per SVG shape. Used by
  LuaLaTeX, Chrome and Windows.
- `SVG `: the same layers as SVG documents. Used by Safari/Core Text,
  Adobe apps and Firefox.
- `cmap`: each bullet's PUA code point, plus every character used in a key.
  A character that is itself a key (`F`, `7`, `-`) maps directly to its
  bullet. Other characters (`d`, `.`, lower case) map to a hollow box, so
  typos are visible.
- `GSUB`: every multi-character key is a ligature. The lookup is
  registered as `rlig`, `liga` and `calt`. The longest key wins: `SIRd`
  beats `SIR`, which beats `S`.

Timestamps are fixed, so rebuilding from the same inputs gives
byte-identical fonts.

## 4. Specimens — `make specimens`

`specimens/index.html` shows every bullet, both typed as its key and by
code point. Open it in Safari (SVG table) and Chrome (COLR table) to check
colors, sizes and ligatures. `specimens/` is not committed.

The same specimen is a page of the documentation site. `make site` builds
the site into `site/` with MkDocs (configured in `mkdocs.yml`), and
`make serve` previews it at <http://127.0.0.1:8000>. The site's pages are
the Markdown files in `docs/`. The hooks in `src/nycbullets/mkdocs_hooks.py`
add the specimen page, the credits and the font files. On every push to
`main`, the `docs` GitHub workflow builds the site and publishes it to
GitHub Pages.

## 5. LaTeX package — `make latex`, `make doc`, `make check`

Source: `src/nycbullets/emit_tex.py` and `latex/`.

`make latex` writes these files into `latex/`:

- `nycbullets-sets.def`: the sets and their font files;
- `nycbullets-<set>.def`: each set's key → code point table;
- `nycbullets-keytable-<set>.tex`: a table of each set's bullets for the
  documentation;
- copies of the fonts.

The package itself is `latex/nycbullets.dtx`, which contains both code and
documentation and is managed by l3build (`latex/build.lua`). The `make`
targets below run `make latex` first:

- `make doc` typesets `nycbullets.pdf` and copies it to `docs/`;
- `make check` runs pytest and `l3build check`;
- `make ctan` builds the CTAN archive;
- `make install` installs into your `TEXMFHOME`.

The package looks up bullets by code point (`\char`) rather than through
ligatures, and turns on `luaotfload`'s `colr` feature. It also works with
XeLaTeX, in monochrome.

## Tests

`make check` runs both test suites.

pytest (`tests/`) checks:

- the file-name heuristics;
- that every mapping table has no `TODO` or duplicate entries;
- that every font has all its tables;
- that every key shapes, through HarfBuzz, to exactly its bullet;
- that every code point maps to its bullet.

`l3build check` (`latex/testfiles/`) checks key lookup and the error for an
unknown key.

## Refreshing from Commons

```sh
make download     # see what changed
make mappings     # new files get rows; review data/mappings/*.tsv
make fonts check doc
```
