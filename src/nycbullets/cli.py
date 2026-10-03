"""Command-line entry point: `uv run nycbullets <step>`."""

from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="nycbullets",
        description="Build NYC Subway bullet color fonts from Wikimedia Commons.",
    )
    parser.add_argument(
        "step",
        choices=["download", "map", "build", "tex", "specimen", "all"],
        help="pipeline step to run ('all' runs every step in order)",
    )
    parser.add_argument(
        "--renumber",
        action="store_true",
        help="with 'map': reassign every code point in key order "
             "(changes existing code points; use only before publishing)",
    )
    args = parser.parse_args(argv)

    steps = ["download", "map", "build", "tex", "specimen"]
    for step in steps if args.step == "all" else [args.step]:
        if step == "download":
            from . import commons
            commons.run()
        elif step == "map":
            from . import mapping
            mapping.run(renumber_all=args.renumber)
        elif step == "build":
            from . import fontbuild
            fontbuild.run()
        elif step == "tex":
            from . import emit_tex
            emit_tex.run()
        elif step == "specimen":
            from . import specimen
            specimen.run()


if __name__ == "__main__":
    main()
