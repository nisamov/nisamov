"""Build a self-contained SVG technology grid from data/technologies.json."""

from __future__ import annotations

import concurrent.futures
import json
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "technologies.json"
OUTPUT_FILE = ROOT / "media" / "technology-grid.svg"
SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)
COLUMNS = 7
CELL_WIDTH = 150
ROW_HEIGHT = 88
MARGIN = 18
ICON_SIZE = 30


def load_icon(url: str) -> bytes | None:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "technology-grid-generator/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            if response.status != 200:
                return None
            return response.read()
    except (OSError, urllib.error.URLError, TimeoutError):
        return None


def icon_markup(source: bytes | None, color: str, x: int, y: int) -> str:
    if source:
        try:
            root = ET.fromstring(source)
            view_box = root.attrib.get("viewBox", "0 0 24 24")
            for element in root.iter():
                for key in ("fill", "stroke"):
                    if element.attrib.get(key, "").lower() == "currentcolor":
                        element.set(key, color)
                style = element.attrib.get("style", "")
                if "currentColor" in style:
                    element.set("style", style.replace("currentColor", color))
                href = element.attrib.get("href") or element.attrib.get(
                    "{http://www.w3.org/1999/xlink}href"
                )
                if href and re.match(r"(?:https?:)?//", href):
                    element.attrib.pop("href", None)
                    element.attrib.pop("{http://www.w3.org/1999/xlink}href", None)
            children = "".join(
                ET.tostring(child, encoding="unicode") for child in list(root)
            )
            if children:
                return (
                    f'<svg x="{x}" y="{y}" width="{ICON_SIZE}" '
                    f'height="{ICON_SIZE}" viewBox="{escape(view_box)}" '
                    f'aria-hidden="true">{children}</svg>'
                )
        except ET.ParseError:
            pass

    # A self-contained, colored fallback is used if a logo source is unavailable.
    return (
        f'<svg x="{x}" y="{y}" width="{ICON_SIZE}" height="{ICON_SIZE}" '
        f'viewBox="0 0 24 24" aria-hidden="true">'
        f'<circle cx="12" cy="12" r="10" fill="{color}" />'
        '<path d="M7 12h10M12 7v10" stroke="#fff" stroke-width="2" '
        'stroke-linecap="round" /></svg>'
    )


def wrap_label(name: str, max_chars: int = 22) -> list[str]:
    words = name.split()
    lines: list[str] = []
    line = ""
    for word in words:
        if line and len(line) + len(word) + 1 > max_chars:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        lines.append(line)
    return lines or [name]


def main() -> None:
    entries = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    unique: dict[str, dict[str, str]] = {}
    for entry in entries:
        key = entry["name"].casefold()
        if key in unique:
            raise ValueError(f"Duplicate technology name (case-insensitive): {entry['name']}")
        unique[key] = entry
    entries = sorted(unique.values(), key=lambda item: item["name"].casefold())

    urls = sorted({entry["icon"] for entry in entries})
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
        icon_sources = dict(zip(urls, executor.map(load_icon, urls)))

    failures = sorted({entry["icon"] for entry in entries if icon_sources[entry["icon"]] is None})
    width = MARGIN * 2 + COLUMNS * CELL_WIDTH
    rows = (len(entries) + COLUMNS - 1) // COLUMNS
    height = MARGIN * 2 + rows * ROW_HEIGHT
    parts = [
        f'<svg xmlns="{SVG_NS}" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" '
        'aria-labelledby="grid-title grid-desc">',
        '<title id="grid-title">Technologies</title>',
        f'<desc id="grid-desc">A grid of {len(entries)} technology logos and labels.</desc>',
        '<style>.label{fill:#24292f;font:12px Arial,sans-serif}'
        '@media(prefers-color-scheme:dark){.label{fill:#f0f6fc}}</style>',
    ]
    for index, entry in enumerate(entries):
        column = index % COLUMNS
        row = index // COLUMNS
        cell_x = MARGIN + column * CELL_WIDTH
        cell_y = MARGIN + row * ROW_HEIGHT
        icon_x = cell_x + (CELL_WIDTH - ICON_SIZE) // 2
        parts.append(
            f'<g aria-label="{escape(entry["name"])}">'
            + icon_markup(
                icon_sources[entry["icon"]],
                entry["color"],
                icon_x,
                cell_y + 5,
            )
        )
        lines = wrap_label(entry["name"])
        first_y = cell_y + 53 if len(lines) == 1 else cell_y + 48
        for line_index, line in enumerate(lines[:2]):
            parts.append(
                f'<text class="label" x="{cell_x + CELL_WIDTH // 2}" '
                f'y="{first_y + line_index * 14}" text-anchor="middle">'
                f'{escape(line)}</text>'
            )
        parts.append("</g>")
    parts.append("</svg>")
    OUTPUT_FILE.write_text("\n".join(parts) + "\n", encoding="utf-8")

    # Validate that the emitted artifact parses and contains no remote image references.
    generated = OUTPUT_FILE.read_text(encoding="utf-8")
    ET.fromstring(generated)
    if re.search(r"(?:href|src)=['\"](?:https?:)?//", generated, flags=re.IGNORECASE):
        raise ValueError("Generated SVG contains an external image reference")
    labels = re.findall(r'<g aria-label="([^"]+)">', generated)
    if len(labels) != len(entries) or len({label.casefold() for label in labels}) != len(labels):
        raise ValueError("Generated SVG labels failed count or uniqueness validation")
    print(f"Generated {OUTPUT_FILE.relative_to(ROOT)} with {len(entries)} technologies.")
    if failures:
        print(f"Used generic inline icons for {len(failures)} unavailable logo sources.")


if __name__ == "__main__":
    main()
