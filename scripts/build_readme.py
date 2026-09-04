"""Refresh the auto-generated blocks in README.md from the GitHub API.

Run by .github/workflows/build-readme.yml on a schedule. Each block in the
README is delimited by `<!-- name starts -->` / `<!-- name ends -->` markers;
everything between them is replaced, everything else is left alone.
"""

import json
import os
import pathlib
import re
import urllib.request
from datetime import datetime, timezone

USER = "arunherga"
ROOT = pathlib.Path(__file__).parent.parent
README = ROOT / "README.md"
MAX_ROWS = 5


def api(path):
    request = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"{USER}-readme-builder",
            **({"Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}"}
               if os.environ.get("GITHUB_TOKEN") else {}),
        },
    )
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def humanise(timestamp):
    """'2026-08-28T13:46:45Z' -> '2 weeks ago'."""
    then = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    days = (datetime.now(timezone.utc) - then).days
    if days < 1:
        return "today"
    if days == 1:
        return "yesterday"
    for size, unit in ((365, "year"), (30, "month"), (7, "week")):
        if days >= size:
            n = days // size
            return f"{n} {unit}{'s' if n > 1 else ''} ago"
    return f"{days} days ago"


def own_repos():
    repos = api(f"/users/{USER}/repos?per_page=100&sort=pushed")
    return [r for r in repos if not r["fork"] and r["name"] != USER]


def recent_releases(repos):
    """Latest release of each repo that has one, newest first."""
    releases = []
    for repo in repos:
        published = api(f"/repos/{USER}/{repo['name']}/releases?per_page=1")
        if published:
            latest = published[0]
            releases.append((latest["published_at"], (
                f"[{repo['name']} {latest['tag_name']}]({latest['html_url']}) "
                f"- {humanise(latest['published_at'])}"
            )))
    releases.sort(reverse=True)
    return [line for _, line in releases[:MAX_ROWS]]


def recently_active(repos):
    lines = []
    for repo in repos[:MAX_ROWS]:
        detail = f" - {repo['language']}" if repo["language"] else ""
        lines.append(
            f"[{repo['name']}]({repo['html_url']}){detail} "
            f"- {humanise(repo['pushed_at'])}"
        )
    return lines


def replace_block(text, name, lines):
    body = "\n\n".join(lines) if lines else "_Nothing yet._"
    pattern = re.compile(
        rf"(<!-- {name} starts -->).*?(<!-- {name} ends -->)", re.DOTALL
    )
    if not pattern.search(text):
        raise SystemExit(f"README is missing the '{name}' markers")
    return pattern.sub(rf"\1\n{body}\n\2", text)


def main():
    repos = own_repos()
    text = README.read_text(encoding="utf-8")
    text = replace_block(text, "recent_releases", recent_releases(repos))
    text = replace_block(text, "recently_active", recently_active(repos))
    README.write_text(text, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
