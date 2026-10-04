# NYC Subway Bullets fonts

<p class="specimen-b f-std">1 2 3 A C E 7d SIR</p>

OpenType color fonts of the New York City Subway route bullets, plus a
LaTeX package (`nycbullets`) for using them. See every bullet in the
[specimen](specimen.md).

> You must take the <span class="f-std lyric-bullet">A</span> train<br>
> To go to Sugar Hill way up in Harlem
>
> — Ella Fitzgerald

<!-- separate the two quotations -->

> Same faces every day, but you don't know their names<br>
> Party people going places on the <span class="f-std lyric-bullet">D</span> train
>
> — Beastie Boys

The artwork comes from the
[New York City Subway bullets](https://commons.wikimedia.org/wiki/Category:New_York_City_Subway_bullets)
collection on Wikimedia Commons. Nearly all of it is in the public domain;
the exceptions are listed in the [credits](credits.md). Each Commons set
becomes one font:

| Font                                                              | Commons set                  |
|-------------------------------------------------------------------|------------------------------|
| [NYCSubwayBullets-Standard.ttf](fonts/NYCSubwayBullets-Standard.ttf)   | Standard set                 |
| [NYCSubwayBullets-Helvetica.ttf](fonts/NYCSubwayBullets-Helvetica.ttf) | Helvetica set                |
| [NYCSubwayBullets-NYCTA.ttf](fonts/NYCSubwayBullets-NYCTA.ttf)         | NYCTA Standard Medium set    |
| [NYCSubwayBullets-R62A.ttf](fonts/NYCSubwayBullets-R62A.ttf)           | R62A                         |
| [NYCSubwayBullets-R32.ttf](fonts/NYCSubwayBullets-R32.ttf)             | R32                          |
| [NYCSubwayBullets-Retired.ttf](fonts/NYCSubwayBullets-Retired.ttf)     | Retired (with subcategories) |
| [NYCSubwayBullets-Legacy.ttf](fonts/NYCSubwayBullets-Legacy.ttf)       | Legacy set                   |
| [NYCSubwayBullets-All.ttf](fonts/NYCSubwayBullets-All.ttf)             | all of the above, each once  |

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
are in the [specimen](specimen.md) and in the
[package documentation](nycbullets.pdf).

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

See the [package documentation](nycbullets.pdf). To install it into your
`TEXMFHOME`, run `make install` in a checkout of the
[repository](https://github.com/nyumathclinic/nyc-subway-bullets-font).

## Rebuilding

The whole pipeline is scripted and reproducible:

```sh
make all     # download → key tables → fonts → specimens → LaTeX docs
make check   # Python and l3build tests
```

See [Building the fonts](PIPELINE.md) for what each step does, how to edit
the keys, and how to refresh from Commons.
