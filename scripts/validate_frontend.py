#!/usr/bin/env python3
"""Fail CI on malformed local references, duplicate IDs, or invalid inline JS."""
from __future__ import annotations
import re
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"

class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.references: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("id"):
            self.ids.append(values["id"] or "")
        if tag in {"a", "link", "script"}:
            reference = values.get("href") or values.get("src")
            if reference:
                self.references.append(reference)

def validate_page(page: Path) -> list[str]:
    errors: list[str] = []
    source = page.read_text(encoding="utf-8")
    parser = PageParser()
    parser.feed(source)
    parser.close()
    duplicates = sorted({item for item in parser.ids if parser.ids.count(item) > 1})
    if duplicates:
        errors.append(f"{page.name}: duplicate IDs: {', '.join(duplicates)}")
    for reference in parser.references:
        if reference.startswith(("http://", "https://", "#", "mailto:")):
            continue
        target = (page.parent / reference.split("#", 1)[0]).resolve()
        if not target.is_file() or FRONTEND.resolve() not in target.parents:
            errors.append(f"{page.name}: missing or unsafe local reference: {reference}")
    scripts = re.findall(r"<script(?:\s[^>]*)?>(.*?)</script>", source, re.DOTALL)
    for index, script in enumerate(scripts, 1):
        if not script.strip():
            continue
        result = subprocess.run(["node", "--check", "-"], input=script, text=True, capture_output=True, check=False)
        if result.returncode:
            errors.append(f"{page.name}: inline script {index}: {result.stderr.strip()}")
    return errors

def main() -> int:
    pages = sorted(FRONTEND.glob("*.html"))
    if not pages:
        print("No frontend HTML pages found", file=sys.stderr)
        return 1
    errors = [error for page in pages for error in validate_page(page)]
    css = FRONTEND / "css" / "styles.css"
    if not css.is_file():
        errors.append("Missing frontend/css/styles.css")
    else:
        source = css.read_text(encoding="utf-8")
        if source.count("{") != source.count("}"):
            errors.append("styles.css: unbalanced braces")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"Validated {len(pages)} HTML pages and shared CSS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
