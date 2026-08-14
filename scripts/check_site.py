#!/usr/bin/env python3
"""Dependency-free integrity checks for the static MNCS Atlas site."""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"


class LinkCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: set[str] = set()
        self.refs: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        element_id = values.get("id")
        if element_id:
            self.ids.add(element_id)
        for attr in ("href", "src"):
            value = values.get(attr)
            if value:
                self.refs.append((attr, value))


def load_html(path: Path) -> LinkCollector:
    parser = LinkCollector()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser


def check() -> list[str]:
    errors: list[str] = []
    html_files = sorted(SITE.rglob("*.html"))
    if not html_files:
        return ["site/ contains no HTML files"]

    parsed = {path: load_html(path) for path in html_files}

    for page, collector in parsed.items():
        for attr, raw_ref in collector.refs:
            ref = raw_ref.strip()
            parts = urlsplit(ref)

            if parts.scheme or parts.netloc or ref.startswith(("mailto:", "tel:", "javascript:")):
                continue

            target_path = page if not parts.path else (page.parent / unquote(parts.path)).resolve()
            try:
                target_path.relative_to(SITE.resolve())
            except ValueError:
                errors.append(f"{page.relative_to(ROOT)}: {attr} escapes site/: {ref}")
                continue

            if parts.path and not target_path.exists():
                errors.append(f"{page.relative_to(ROOT)}: missing local target: {ref}")
                continue

            if parts.fragment:
                fragment = unquote(parts.fragment)
                if target_path.suffix.lower() == ".html" or target_path == page.resolve():
                    target_page = target_path if target_path.suffix.lower() == ".html" else page
                    target = parsed.get(target_page)
                    if target is None and target_page.exists():
                        target = load_html(target_page)
                    if target is not None and fragment not in target.ids:
                        errors.append(
                            f"{page.relative_to(ROOT)}: missing fragment #{fragment} in {target_page.relative_to(ROOT)}"
                        )

    required = [
        SITE / "index.html",
        SITE / "assets" / "styles.css",
        SITE / "assets" / "app.js",
    ]
    for path in required:
        if not path.is_file():
            errors.append(f"missing required site file: {path.relative_to(ROOT)}")

    return errors


def main() -> int:
    errors = check()
    if errors:
        print("MNCS Atlas site checks failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("MNCS Atlas site checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
