"""
Attribution for bullets whose license requires it.

Most of the artwork is in the public domain (or CC0), but a few files are
under licenses such as CC BY 4.0 that require crediting the author.  The
license and author of every file come from sources/manifest.json, as
reported by Commons.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .config import MANIFEST, needs_credit


@dataclass(frozen=True)
class Credit:
    file: str
    artist: str
    license: str
    page: str

    @property
    def title(self) -> str:
        return Path(self.file).stem

    def __str__(self) -> str:
        return f'"{self.title}" by {self.artist}, {self.license}, {self.page}'


def credits_for(files: list[str] | set[str]) -> list[Credit]:
    """The credits required for the given files, sorted by file name."""

    manifest = json.loads(MANIFEST.read_text())["files"]
    result = []
    for name in sorted(files, key=str.casefold):
        meta = manifest[name]
        if needs_credit(meta["license"]):
            result.append(Credit(name, meta["artist"] or "unknown",
                                 meta["license"], meta["page"]))
    return result
