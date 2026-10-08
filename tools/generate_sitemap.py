#!/usr/bin/env python3
"""
Generate sitemap.xml from what is actually on disk.

Run from the repo root:  python3 tools/generate_sitemap.py
`--check` writes nothing and exits 1 if sitemap.xml's URLs, order or priorities differ
from what would be generated, if a <lastmod> element is missing, or if one is more than
a day OLDER than the page's last change. Exact lastmod equality is deliberately not
required: generation stamps a dirty page with today's date and a clean checkout derives
it from the commit's author date, so the two legitimately differ by a day or so (late
commit, rebase). A squash-merge days after generation would trip it; regenerate then.

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


def ld_nodes(data):
    """Yield every dict node anywhere in a parsed JSON-LD value.

    JSON-LD is legally a single object, an array of objects, an object
    carrying an @graph array, or nodes nested under properties such as
    mainEntity. Treating it as always-a-dict crashed the whole run on an
    array and silently dropped the ordering date for @graph and nested nodes.
    """
    if isinstance(data, dict):
        yield data
        for value in data.values():
            yield from ld_nodes(value)
    elif isinstance(data, list):
        for item in data:
            yield from ld_nodes(item)


def date_value(value):
    """datePublished as a string, or None. JSON-LD also allows {"@value": ...};
    anything else is treated as undated so the sort key is always a string."""
    if isinstance(value, dict):
        value = value.get("@value")
    return value if isinstance(value, str) and value else None


def page_facts(repo, path, warnings):
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
            warnings.append(f"{name} has unparseable JSON-LD")
            continue
        published = next(
            (d for d in (date_value(n.get("datePublished")) for n in ld_nodes(data)) if d),
            None,
        )
        if published:
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


def strip_lastmod(xml):
    return re.sub(r"<lastmod>[^<]*</lastmod>", "<lastmod/>", xml)


def main():
    args = [a for a in sys.argv[1:] if a != "--check"]
    unknown = [a for a in args if a.startswith("--")]
    if unknown:
        print(f"unknown option: {unknown[0]}", file=sys.stderr)
        return 2
    check = len(args) != len(sys.argv) - 1
    repo = os.path.abspath(args[0]) if args else os.getcwd()

    pages = []
    problems = []
    warnings = []
    for path in sorted(glob.glob(os.path.join(repo, "*.html"))):
        name = os.path.basename(path)
        facts = page_facts(repo, path, warnings)
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

    if not any(p["name"] == "index.html" for p in pages):
        problems.append(f"no index.html found in {repo}: wrong directory?")

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

    rendered = "\n".join(lines) + "\n"
    out = os.path.join(repo, "sitemap.xml")

    if check:
        for warning in warnings:
            print(f"WARNING: {warning}")
        current = open(out, encoding="utf-8").read() if os.path.exists(out) else ""
        if strip_lastmod(current) != strip_lastmod(rendered):
            print("sitemap.xml is out of date (URLs, order, priority or a missing <lastmod>): run "
                  "python3 tools/generate_sitemap.py and commit the result",
                  file=sys.stderr)
            return 1
        # Exact lastmod equality is not checkable (see the docstring), but
        # "older than the page's real change" is the defect this tool exists
        # to kill, so a stored date more than a day behind the derived one fails.
        stored = re.findall(r"<lastmod>([^<]*)</lastmod>", current)
        derived = re.findall(r"<lastmod>([^<]*)</lastmod>", rendered)
        if len(stored) != len(derived):
            print("sitemap.xml has missing or extra <lastmod> elements", file=sys.stderr)
            return 1
        for have, want in zip(stored, derived):
            try:
                behind = (datetime.date.fromisoformat(want)
                          - datetime.date.fromisoformat(have)).days
            except ValueError:
                behind = 99
            if behind > 1:
                print(f"sitemap.xml <lastmod> {have} is older than the page's "
                      f"last change {want}: regenerate", file=sys.stderr)
                return 1
        print("sitemap.xml is current")
        return 0

    with open(out, "w", encoding="utf-8") as handle:
        handle.write(rendered)

    print(f"Wrote {out} — {len(pages)} URLs "
          f"({len(home)} home, {len(essays)} essays, {len(about)} about)")
    # Warnings go to STDOUT on purpose: publish_essay.py logs stdout on success
    # and drops stderr unless the run fails, so a stderr warning never reached
    # anyone.
    for warning in warnings:
        print(f"WARNING: {warning}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
