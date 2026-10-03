"""Project paths and the bullet-set configuration (config/sets.toml)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path


def _find_root() -> Path:
    """The project directory: the current directory if it has a
    config/sets.toml (so the pipeline can run on a copy of the project),
    otherwise the checkout this package lives in."""

    cwd = Path.cwd()
    if (cwd / "config" / "sets.toml").exists():
        return cwd
    return Path(__file__).resolve().parents[2]


ROOT = _find_root()

CONFIG_FILE = ROOT / "config" / "sets.toml"
SOURCE_DIR = ROOT / "sources" / "commons"
OUTLINED_DIR = ROOT / "sources" / "outlined"
MANIFEST = ROOT / "sources" / "manifest.json"
MAPPING_DIR = ROOT / "data" / "mappings"
FONT_DIR = ROOT / "fonts"
LATEX_DIR = ROOT / "latex"
SPECIMEN_DIR = ROOT / "specimens"

FAMILY = "NYC Subway Bullets"
PS_FAMILY = "NYCSubwayBullets"


@dataclass(frozen=True)
class BulletSet:
    id: str
    name: str
    categories: list[str] = field(default_factory=list)
    recurse: bool = False

    @property
    def family(self) -> str:
        return f"{FAMILY} {self.name}"

    @property
    def ps_name(self) -> str:
        return f"{PS_FAMILY}-{self.name}"

    @property
    def font_file(self) -> Path:
        return FONT_DIR / f"{self.ps_name}.ttf"

    @property
    def mapping_file(self) -> Path:
        return MAPPING_DIR / f"{self.id}.tsv"


def allowed_licenses() -> list[str]:
    return list(tomllib.loads(CONFIG_FILE.read_text())["allowed_licenses"])


def needs_credit(license: str) -> bool:
    """Whether a license requires attribution (anything but PD/CC0)."""

    return license not in ("Public domain", "CC0")


def load_config() -> tuple[list[BulletSet], BulletSet]:
    """Return (the individual sets in priority order, the All set)."""

    data = tomllib.loads(CONFIG_FILE.read_text())
    sets = [
        BulletSet(
            id=s["id"],
            name=s["name"],
            categories=list(s["categories"]),
            recurse=bool(s.get("recurse", False)),
        )
        for s in data["set"]
    ]
    all_set = BulletSet(id=data["all"]["id"], name=data["all"]["name"])
    return sets, all_set
