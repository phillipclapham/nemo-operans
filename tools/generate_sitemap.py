#!/usr/bin/env python3
"""
Generate sitemap.xml from what is actually on disk.

Run from the repo root:  python3 tools/generate_sitemap.py

The hand-maintained sitemap drifted two months and six essays out of date, and
its homepage <lastmod> ended up OLDER than the homepage's real last change --
which is precisely the signal that tells a crawler not to re-fetch a page whose
structured data had just been corrected. Hand-editing it once only resets the
clock on the same failure, so it is derived instead.

Authorities, in order:
  URL        <- each page's og:url meta tag, never the filename. The site is
                served extensionless and the og:url is what the page itself
                claims to be.
  lastmod    <- the last git commit touching that file, or TODAY if the file
                has uncommitted changes. The second half matters: this runs
                mid-publish, before the new essay is committed.
  published  <- datePublished from the page's JSON-LD, used only for ordering.

Ordering is homepage, then essays newest-published first, then about -- stable
across runs so the file does not churn on every regeneration.
"""

import datetime
import glob
import json
import os
import re
import subprocess
import sys
import xml.sax.saxutils as saxutils

SITE = "https://nemooperans.com"
LD_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)


def today():
    return datetime.date.today().isoformat()


def git_last_modified(repo, filename):
    """Date this file last changed.

    Uncommitted changes count as TODAY, and this is the load-bearing part.
    publish_essay.py regenerates the sitemap AFTER writing the new essay and
    updating index.html but BEFORE committing them, so asking git alone gives
    the new essay no date at all and reports the homepage's PREVIOUS commit
    date -- reproducing the exact defect this generator exists to kill: a
    lastmod older than the page's real change, which tells crawlers not to
    re-fetch a page that just changed.
    """
    status = subprocess.run(
        ["git", "status", "--porcelain", "--", filename],
        cwd=repo, capture_output=True, text=True,
    ).stdout.strip()
    if status:
        return today()

    out = subprocess.run(
        ["git", "log", "-1", "--format=%ad", "--date=short", "--", filename],
        cwd=repo, capture_output=True, text=True,
    ).stdout.strip()
    # Untracked-but-unreported, or a repo with no history yet.
    return out or today()


def page_facts(repo, path):
    name = os.path.basename(path)
    source = open(path, encoding="utf-8").read()

    og = re.search(r'og:url"\s+content="([^"]+)"', source)
    if not og:
        return None
    url = og.group(1)
    # A bare origin is canonically written with a trailing slash in a sitemap.
    if url.rstrip("/") == SITE:
        url = SITE + "/"

    published = None
    for block in LD_RE.findall(source):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            # A page whose JSON-LD does not parse still belongs in the sitemap;
            # it just cannot contribute an ordering date.
            print(f"  warning: {name} has unparseable JSON-LD", file=sys.stderr)
            continue
        if data.get("datePublished"):
            published = data["datePublished"]
            break

    return {
        "name": name,
        "url": url,
        "lastmod": git_last_modified(repo, name),
        "published": published,
        "priority": "1.0" if name == "index.html"
        else "0.8" if name == "about.html"
        else "0.9",
    }


def main():
    repo = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.getcwd()

    pages = []
    problems = []
    for path in sorted(glob.glob(os.path.join(repo, "*.html"))):
        name = os.path.basename(path)
        facts = page_facts(repo, path)
        if facts is None:
            # og:url is the URL authority, so a page without one cannot be
            # placed. Silently dropping it would quietly shrink the sitemap --
            # the same invisible-omission failure the old hand-edited file had.
            problems.append(f"{name}: no og:url, cannot determine its URL")
            continue
        pages.append(facts)

    # This file auto-deploys. Refuse to emit a sitemap that points off-site or
    # lists the same URL twice rather than publishing a broken one.
    seen = {}
    for page in pages:
        if not page["url"].startswith(SITE + "/"):
            problems.append(f"{page['name']}: og:url is off-site — {page['url']}")
        if page["url"] in seen:
            problems.append(
                f"{page['name']}: duplicate og:url with {seen[page['url']]} "
                f"— {page['url']}"
            )
        seen[page["url"]] = page["name"]

    if problems:
        print("REFUSING to write sitemap.xml:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        return 1

    home = [p for p in pages if p["name"] == "index.html"]
    about = [p for p in pages if p["name"] == "about.html"]
    essays = [p for p in pages if p["name"] not in ("index.html", "about.html")]
    # Undated essays sort last rather than crashing the comparison.
    essays.sort(key=lambda p: (p["published"] or "", p["name"]), reverse=True)

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for page in home + essays + about:
        lines.append("  <url>")
        lines.append(f"    <loc>{saxutils.escape(page['url'])}</loc>")
        if page["lastmod"]:
            lines.append(f"    <lastmod>{page['lastmod']}</lastmod>")
        lines.append(f"    <priority>{page['priority']}</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")

    out = os.path.join(repo, "sitemap.xml")
    with open(out, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")

    print(f"Wrote {out} — {len(pages)} URLs "
          f"(1 home, {len(essays)} essays, {len(about)} about)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
