# NYC Subway Bullets fonts

OpenType color fonts of the New York City Subway route bullets, plus a
LaTeX package (`nycbullets`) for using them. See every bullet in the
[specimen](https://nyumathclinic.github.io/nyc-subway-bullets-font/specimen/).

The artwork comes from the
[New York City Subway bullets](https://commons.wikimedia.org/wiki/Category:New_York_City_Subway_bullets)
collection on Wikimedia Commons. Nearly all of it is in the public domain;
the exceptions are credited in [fonts/CREDITS.md](fonts/CREDITS.md). Each
Commons set becomes one font:

| Font file                              | Commons set                     |
|----------------------------------------|---------------------------------|
| `fonts/NYCSubwayBullets-Standard.ttf`  | Standard set                    |
| `fonts/NYCSubwayBullets-Helvetica.ttf` | Helvetica set                   |
| `fonts/NYCSubwayBullets-NYCTA.ttf`     | NYCTA Standard Medium set       |
| `fonts/NYCSubwayBullets-R62A.ttf`      | R62A                            |
| `fonts/NYCSubwayBullets-R32.ttf`       | R32                             |
| `fonts/NYCSubwayBullets-Retired.ttf`   | Retired (with subcategories)    |
| `fonts/NYCSubwayBullets-Legacy.ttf`    | Legacy set                      |
| `fonts/NYCSubwayBullets-All.ttf`       | all of the above, each once     |

All the fonts, with their credits and licenses, can be downloaded at once
as [NYCSubwayBullets.zip](https://nyumathclinic.github.io/nyc-subway-bullets-font/fonts/NYCSubwayBullets.zip).

Each font contains three versions of every bullet. Applications use the
one they support:

- a **COLR/CPAL** color table, used by LuaLaTeX, Chrome and Windows;
- an **SVG** color table, used by Safari, macOS and Adobe applications;
- **monochrome outlines** as a fallback.

## Typing bullets

Type the route's **key**. The keys are ligatures, so they work in any
application that applies standard ligatures:

| key        | bullet                                   |
|------------|------------------------------------------|
| `F`        | F, circle (local)                        |
| `Fd`       | F, diamond (express)                     |
| `SIR`      | Staten Island Railway                    |
| `M.brown`  | variant: brown M                         |
| `-`        | dash bullet                              |

Separate adjacent bullets with spaces: `A C E`, not `ACE`. Every bullet
also has a Private Use Area code point. The full key and code point tables
are in [docs/nycbullets.pdf](docs/nycbullets.pdf) and
[data/mappings/](data/mappings/).

In the All font, keys outside the Standard set carry a set tag after the
route, e.g. `F.helv` or `B.nycta.broadway`.

## LaTeX

```latex
% compile with lualatex
\usepackage{nycbullets}
...
Take the \nycbullet{F} or \nycbullet{Fd} to Coney Island.
\nycbullet[helvetica]{M.brown}
```

See [docs/nycbullets.pdf](docs/nycbullets.pdf). To install it into your
`TEXMFHOME`, run `make install`.

## Rebuilding

The whole pipeline is scripted and reproducible:

```sh
make all     # download → key tables → fonts → specimens → LaTeX docs
make check   # Python and l3build tests
```

See [docs/PIPELINE.md](docs/PIPELINE.md) for what each step does, how to
edit the keys, and how to refresh from Commons.

## License

| Component                                              | License                                  |
|--------------------------------------------------------|------------------------------------------|
| Python pipeline (`src/`, `tests/`, build files)        | [MIT](LICENSE)                           |
| LaTeX package (`latex/`)                               | [LPPL 1.3c](LICENSES/LPPL-1.3c.txt) or later |
| Fonts (`fonts/*.ttf`)                                  | [CC0 1.0](LICENSES/CC0-1.0.txt), except the bullets credited in [fonts/CREDITS.md](fonts/CREDITS.md), which keep their own licenses |
| Key tables and configuration (`data/`, `config/`)      | [CC0 1.0](LICENSES/CC0-1.0.txt)          |
| Documentation (`docs/`, this README)                   | [CC BY 4.0](LICENSES/CC-BY-4.0.txt)      |
| Downloaded artwork (`sources/`)                        | as recorded for each file in `sources/manifest.json` (public domain or CC BY 4.0) |

Not affiliated with or endorsed by the MTA; the bullets may be trademarks
of the MTA.
