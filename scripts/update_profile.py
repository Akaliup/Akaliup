#!/usr/bin/env python3
"""Regenerate the profile README contribution block and the stats card.

Reads public GitHub data only (search API), so it needs no scraping and no
personal access token beyond the default GITHUB_TOKEN. Run locally with:

    GH_TOKEN=$(gh auth token) python scripts/update_profile.py

Every generated section sits between HTML comment markers in README.md, so
hand-written prose outside the markers is never touched.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

USER = "Akaliup"
ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
STATS_SVG = ROOT / "assets" / "open-source-stats.svg"

START = "<!-- OPEN_SOURCE_CONTRIBUTIONS:START -->"
END = "<!-- OPEN_SOURCE_CONTRIBUTIONS:END -->"

API = "https://api.github.com"


def token() -> str:
    value = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not value:
        sys.exit("GH_TOKEN or GITHUB_TOKEN is required")
    return value


def search(query: str, token_value: str) -> list[dict]:
    params = urllib.parse.urlencode(
        {"q": query, "per_page": 100, "sort": "updated", "order": "desc"}
    )
    request = urllib.request.Request(
        f"{API}/search/issues?{params}",
        headers={
            "Authorization": f"Bearer {token_value}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": USER,
        },
    )
    with urllib.request.urlopen(request) as response:
        return json.load(response).get("items", [])


def repo_of(item: dict) -> str:
    """owner/name from the repository_url field."""
    return item["repository_url"].split("/repos/")[-1]


def external(scope: str, token_value: str) -> list[dict]:
    return search(f"is:pr {scope} author:{USER} -user:{USER}", token_value)


def sort_key(item: dict) -> tuple[str, int]:
    """Stable order: the search API's "recently updated" order flips rows
    between runs, which would commit noise every day."""
    return (repo_of(item).lower(), item["number"])


def one_line(title: str) -> str:
    text = " ".join(title.split())
    if len(text) <= 84:
        return text
    cut = text[:84].rsplit(" ", 1)[0].rstrip(",;:-")
    return cut + "..."


def describe(title: str) -> str:
    """Turn a conventional-commit title into a short sentence."""
    head, _, rest = title.partition(":")
    if rest and len(head) <= 20 and " " not in head:
        text = rest.strip()
    else:
        text = title
    text = text.strip()
    return text[:1].upper() + text[1:] if text else text


def table(rows: list[dict]) -> str:
    lines = ["| Project | Contribution | PR |", "|---|---|---|"]
    for item in rows:
        repo = repo_of(item)
        lines.append(
            f"| [{repo}](https://github.com/{repo}) "
            f"| {describe(one_line(item['title']))} "
            f"| [#{item['number']}]({item['html_url']}) |"
        )
    return "\n".join(lines)


def build_block(merged: list[dict], review: list[dict], issues: list[dict]) -> str:
    stamp = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
    shown = review[:8]
    parts = [START, "## Open Source Contributions", ""]
    parts.append(
        f"> Updated {stamp} · **{len(merged)}** merged · "
        f"**{len(review)}** in review · **{len(issues)}** issues filed"
    )
    parts.append("")
    parts.append("### Merged Pull Requests")
    parts.append("")
    parts.append(table(merged) if merged else "_Nothing merged yet._")
    parts.append("")
    parts.append("### Pull Requests In Review")
    parts.append("")
    parts.append(table(shown) if shown else "_Nothing waiting on a reviewer._")
    if len(review) > len(shown):
        parts.append("")
        parts.append(
            f"<sub>…and {len(review) - len(shown)} more open PRs - "
            f"[see them on GitHub](https://github.com/search?q=is%3Apr+author%3A{USER}"
            f"+-user%3A{USER}+is%3Aopen&type=pullrequests)</sub>"
        )
    if issues:
        repos = Counter(repo_of(item).split("/")[-1] for item in issues)
        top = ", ".join(name for name, _ in repos.most_common(3))
        parts.append("")
        parts.append(
            f"Also reported **{len(issues)}** issues upstream (mostly {top})."
        )
    parts.append("")
    parts.append(END)
    return "\n".join(parts)


def bar(value: int, widest: int, width: int = 240) -> int:
    if widest <= 0:
        return 0
    return max(6, round(value / widest * width))


def build_svg(merged: list[dict], review: list[dict], issues: list[dict]) -> str:
    counts = Counter()
    for item in merged + review:
        counts[repo_of(item).split("/")[-1]] += 1
    top = counts.most_common(5)
    widest = top[0][1] if top else 0

    rows = []
    for index, (name, value) in enumerate(top):
        y = 150 + index * 26
        rows.append(
            f'<text x="56" y="{y}" fill="#8b949e" font-size="13" '
            f'font-family="ui-monospace, SFMono-Regular, Menlo, monospace">{name}</text>'
        )
        rows.append(
            f'<rect x="196" y="{y - 11}" width="240" height="9" rx="4.5" fill="#161b22"/>'
        )
        rows.append(
            f'<rect x="196" y="{y - 11}" width="{bar(value, widest)}" height="9" '
            f'rx="4.5" fill="url(#bar)"/>'
        )
        rows.append(
            f'<text x="446" y="{y}" fill="#c9d1d9" font-size="12" '
            f'font-family="ui-monospace, SFMono-Regular, Menlo, monospace">{value}</text>'
        )

    def stat(x: int, value: int, label: str) -> str:
        return (
            f'<text x="{x}" y="96" fill="#e6edf3" font-size="30" font-weight="600" '
            f'font-family="-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif">'
            f"{value}</text>"
            f'<text x="{x}" y="112" fill="#8b949e" font-size="11" letter-spacing="1.2" '
            f'font-family="-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif">'
            f"{label.upper()}</text>"
        )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="520" height="284" viewBox="0 0 520 284" role="img" aria-label="Open source contribution summary: {len(merged)} merged, {len(review)} in review, {len(issues)} issues filed">
  <defs>
    <linearGradient id="bar" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#58a6ff"/>
      <stop offset="100%" stop-color="#a371f7"/>
    </linearGradient>
  </defs>
  <rect width="520" height="284" rx="14" fill="#0d1117" stroke="#30363d"/>
  <text x="28" y="40" fill="#e6edf3" font-size="14" font-weight="600" letter-spacing="1.6"
        font-family="-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif">OPEN SOURCE</text>
  <text x="28" y="58" fill="#6e7681" font-size="11"
        font-family="ui-monospace, SFMono-Regular, Menlo, monospace">upstream repos, not my own</text>
  {stat(28, len(merged), "merged")}
  {stat(146, len(review), "in review")}
  {stat(282, len(issues), "issues")}
  <line x1="28" y1="122" x2="492" y2="122" stroke="#21262d"/>
  {chr(10).join("  " + row for row in rows)}
</svg>
"""


def main() -> None:
    token_value = token()
    merged = sorted(external("is:merged", token_value), key=sort_key)
    review = sorted(external("is:open", token_value), key=sort_key)
    issues = sorted(search(f"is:issue author:{USER} -user:{USER}", token_value), key=sort_key)

    block = build_block(merged, review, issues)
    readme = README.read_text(encoding="utf-8")
    if START not in readme or END not in readme:
        sys.exit(f"README.md is missing the {START} / {END} markers")

    head, _, rest = readme.partition(START)
    _, _, tail = rest.partition(END)
    README.write_text(head + block + tail, encoding="utf-8", newline="\n")

    STATS_SVG.parent.mkdir(parents=True, exist_ok=True)
    STATS_SVG.write_text(
        build_svg(merged, review, issues), encoding="utf-8", newline="\n"
    )

    print(f"merged={len(merged)} review={len(review)} issues={len(issues)}")


if __name__ == "__main__":
    main()
