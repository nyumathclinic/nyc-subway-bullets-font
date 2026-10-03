"""
Download NYC Subway bullet SVGs from Wikimedia Commons.

Every set in config/sets.toml names one or more Commons categories.  We list
the SVG files in each (recursing into subcategories when asked), look up their
download URLs, SHA-1 hashes and license metadata, and download each file once
into sources/commons/.  sources/manifest.json records what we got, so a rerun
only downloads files that are missing locally or have changed on Commons.

The downloader is polite: it identifies itself with a User-Agent, pauses a
random interval between downloads, and backs off when the server answers
429 Too Many Requests.
"""

from __future__ import annotations

import functools
import hashlib
import json
import os
import random
import re
import sys
import time
from pathlib import Path

import requests

from .config import MANIFEST, SOURCE_DIR, load_config

API_URL = "https://commons.wikimedia.org/w/api.php"

# Wikimedia's User-Agent policy asks clients to identify themselves and give
# contact information (an email address or a URL).  Set NYCBULLETS_CONTACT
# to use a different contact.
CONTACT = os.environ.get("NYCBULLETS_CONTACT", "mleingang@gmail.com").strip()
USER_AGENT = (
    f"nyc-subway-bullet-font/1.0 "
    f"(OpenType color font builder{'; ' + CONTACT if CONTACT else ''}) "
    f"python-requests/{requests.__version__}"
)

# Seconds to pause between downloads (a random value in this range).
# Override with NYCBULLETS_DELAY="min,max".
DELAY = tuple(
    float(x) for x in os.environ.get("NYCBULLETS_DELAY", "10,20").split(",")
)

print = functools.partial(print, flush=True)

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _get(url: str, **kwargs) -> requests.Response:
    """GET with retries on 429 Too Many Requests."""

    for attempt in range(12):
        response = session.get(url, timeout=30, **kwargs)

        if response.status_code != 429:
            break

        retry_after = response.headers.get("Retry-After", "")
        wait = int(retry_after) if retry_after.isdigit() else 2 ** attempt * 5
        wait += random.uniform(1, 5)
        print(f"  429 received, waiting {wait:.1f}s", file=sys.stderr)
        time.sleep(wait)

    response.raise_for_status()
    return response


def _api(params: dict) -> dict:
    data = _get(API_URL, params={"format": "json", **params}).json()
    if "error" in data:
        raise RuntimeError(f"Commons API error: {data['error']}")
    return data


# ---------------------------------------------------------------------------
# Category listing
# ---------------------------------------------------------------------------

def _category_members(category: str, cmtype: str) -> list[str]:
    titles = []
    cmcontinue = None

    while True:
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": category,
            "cmtype": cmtype,
            "cmlimit": "max",
        }
        if cmcontinue:
            params["cmcontinue"] = cmcontinue

        data = _api(params)
        titles += [m["title"] for m in data["query"]["categorymembers"]]

        if "continue" not in data:
            break
        cmcontinue = data["continue"]["cmcontinue"]

    return titles


def get_category_files(category: str, recurse: bool = False,
                       _seen: set[str] | None = None) -> list[str]:
    """Return the SVG file titles in a category, optionally recursively."""

    seen = _seen if _seen is not None else set()
    if category in seen:
        return []
    seen.add(category)

    titles = [
        t for t in _category_members(category, "file")
        if t.lower().endswith(".svg")
    ]

    if recurse:
        for sub in _category_members(category, "subcat"):
            titles += get_category_files(sub, recurse=True, _seen=seen)

    return sorted(set(titles), key=str.casefold)


def get_file_info(titles: list[str]) -> dict[str, dict]:
    """Ask Commons for download URL, SHA-1 and license of each file."""

    result = {}

    # The API permits batches of 50 titles.
    for start in range(0, len(titles), 50):
        batch = titles[start:start + 50]
        data = _api({
            "action": "query",
            "prop": "imageinfo",
            "iiprop": "url|sha1|extmetadata",
            "iiextmetadatafilter": "LicenseShortName|Artist",
            "titles": "|".join(batch),
        })

        for page in data["query"]["pages"].values():
            title = page["title"]
            if "imageinfo" not in page:
                print(f"WARNING: no image info for {title}", file=sys.stderr)
                continue

            info = page["imageinfo"][0]
            meta = info.get("extmetadata", {})
            result[title] = {
                "url": info["url"].split("?")[0],
                "page": info["descriptionurl"],
                "sha1": info["sha1"],
                "license": meta.get("LicenseShortName", {}).get("value", ""),
                "artist": _strip_html(meta.get("Artist", {}).get("value", "")),
            }

    return result


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def filename_from_title(title: str) -> str:
    """Convert 'File:NYCS-bull-trans-A.svg' to a local filename."""

    return title.removeprefix("File:")


def sha1_of(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()


def download_file(url: str, destination: Path) -> None:
    destination.write_bytes(_get(url).content)

    # Random pause between downloads to stay under rate limits.
    time.sleep(random.uniform(*DELAY))


def load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text())
    return {"files": {}}


def run() -> None:
    """Download every set's files and write sources/manifest.json."""

    sets, _ = load_config()
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)

    # file title -> list of set ids, in set priority order
    membership: dict[str, list[str]] = {}

    for bset in sets:
        titles: list[str] = []
        for category in bset.categories:
            print(f"Listing {category}{' (recursive)' if bset.recurse else ''}")
            titles += get_category_files(category, recurse=bset.recurse)
        titles = sorted(set(titles), key=str.casefold)
        print(f"  {bset.name}: {len(titles)} SVG files")
        for title in titles:
            membership.setdefault(title, []).append(bset.id)

    print(f"{len(membership)} distinct files; fetching metadata")
    info = get_file_info(sorted(membership, key=str.casefold))

    # Write the manifest before downloading, so that an interrupted run
    # still records what the categories contain.
    files = {
        filename_from_title(title): {
            "title": title,
            **info[title],
            "sets": membership[title],
        }
        for title in sorted(info, key=str.casefold)
    }
    MANIFEST.write_text(
        json.dumps({"files": files}, indent=2, ensure_ascii=False,
                   sort_keys=True) + "\n"
    )

    downloaded = changed = 0
    for index, (filename, meta) in enumerate(files.items(), start=1):
        destination = SOURCE_DIR / filename

        if destination.exists() and sha1_of(destination) == meta["sha1"]:
            continue

        if destination.exists():
            print(f"[{index:3}/{len(files)}] {filename} (changed on Commons)")
            changed += 1
        else:
            print(f"[{index:3}/{len(files)}] {filename}")
        download_file(meta["url"], destination)
        downloaded += 1

        if sha1_of(destination) != meta["sha1"]:
            raise RuntimeError(f"SHA-1 mismatch after download: {filename}")

    # Files that are in the cache but no longer in any category.
    stale = sorted(
        p.name for p in SOURCE_DIR.glob("*.svg") if p.name not in files
    )
    for name in stale:
        print(f"NOTE: {name} is no longer in any configured category")

    print(f"Downloaded {downloaded} file(s) ({changed} changed); "
          f"{len(files)} in manifest.")
