from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import re
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
STATIC_ROOT = PROJECT_ROOT / "app" / "static"
INDEX_HTML = STATIC_ROOT / "index.html"
APP_JS = STATIC_ROOT / "app.js"
APP_CSS = STATIC_ROOT / "app.css"
STATIC_URL_PATTERN = re.compile(r"""["'(](?P<url>/static/[^"'()\s?#]+)""")
CSS_URL_PATTERN = re.compile(r"""url\((?P<quote>["']?)(?P<url>[^)"']+)(?P=quote)\)""")


class StaticHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.static_urls: set[str] = set()
        self.inline_violations: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {name.lower(): value or "" for name, value in attrs}
        for name, value in attr_map.items():
            if name.startswith("on"):
                self.inline_violations.append(f"inline event handler {name!r} on <{tag}>")
            if name in {"href", "src"} and value.startswith("/static/"):
                self.static_urls.add(value)
        if tag == "script" and "src" not in attr_map:
            self.inline_violations.append("inline <script> block")
        if tag == "style":
            self.inline_violations.append("inline <style> block")
        if "style" in attr_map:
            self.inline_violations.append(f"inline style attribute on <{tag}>")


def main() -> int:
    failures: list[str] = []
    html = INDEX_HTML.read_text(encoding="utf-8")
    parser = StaticHtmlParser()
    parser.feed(html)
    failures.extend(parser.inline_violations)
    static_urls = set(parser.static_urls)

    for source_path in (APP_JS, APP_CSS):
        source = source_path.read_text(encoding="utf-8")
        static_urls.update(match.group("url") for match in STATIC_URL_PATTERN.finditer(source))
        if source_path == APP_CSS:
            static_urls.update(
                match.group("url")
                for match in CSS_URL_PATTERN.finditer(source)
                if match.group("url").startswith("/static/")
            )
            if "letter-spacing: -" in source:
                failures.append("negative letter-spacing found in CSS")

    for url in sorted(static_urls):
        path = STATIC_ROOT / url.removeprefix("/static/")
        if not path.is_file():
            failures.append(f"missing static asset referenced by UI: {url}")

    js_source = APP_JS.read_text(encoding="utf-8")
    for opening, closing in (("(", ")"), ("[", "]"), ("{", "}")):
        if js_source.count(opening) != js_source.count(closing):
            failures.append(f"unbalanced JavaScript delimiter pair {opening}{closing}")

    if failures:
        print("Static asset smoke failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(f"Static asset smoke passed: {len(static_urls)} referenced static assets checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
