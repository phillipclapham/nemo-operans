"""Run: python3 -m unittest discover -s tools"""
import os
import subprocess
import sys
import tempfile
import unittest

TOOL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generate_sitemap.py")


def page(url, ld):
    return (f'<html><head><meta property="og:url" content="{url}">'
            f'<script type="application/ld+json">{ld}</script></head></html>')


def run_in(files, *extra):
    with tempfile.TemporaryDirectory() as d:
        for name, body in files.items():
            with open(os.path.join(d, name), "w") as f:
                f.write(body)
        r = subprocess.run([sys.executable, TOOL, d, *extra],
                           capture_output=True, text=True, cwd=d)
        out = open(os.path.join(d, "sitemap.xml")).read() if os.path.exists(
            os.path.join(d, "sitemap.xml")) else ""
        return r, out


HOME = page("https://nemooperans.com/", '{"datePublished":"2026-01-01"}')


class SitemapTests(unittest.TestCase):
    def test_list_and_graph_shaped_jsonld_do_not_crash(self):
        # Reproduced 2026-10-07: [{"@type":"WebPage"}] -> AttributeError.
        r, out = run_in({
            "index.html": HOME,
            "a.html": page("https://nemooperans.com/a", '[{"@type":"WebPage"},{"datePublished":"2026-03-01"}]'),
            "b.html": page("https://nemooperans.com/b", '{"@graph":[{"datePublished":"2026-05-01"}]}'),
        })
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertLess(out.index("/b<"), out.index("/a<"))  # newest first: b (2026-05) before a (2026-03)

    def test_unparseable_jsonld_warning_reaches_stdout(self):
        # publish_essay.py logs stdout on rc==0 and drops stderr.
        r, _ = run_in({"index.html": HOME, "a.html": page("https://nemooperans.com/a", "{not json")})
        self.assertEqual(r.returncode, 0)
        self.assertIn("WARNING: a.html has unparseable JSON-LD", r.stdout)

    def test_non_string_datepublished_does_not_crash(self):
        r, _ = run_in({
            "index.html": HOME,
            "a.html": page("https://nemooperans.com/a", '{"datePublished":{"@value":"2026-03-01"}}'),
            "b.html": page("https://nemooperans.com/b", '{"datePublished":20260301}'),
        })
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_check_passes_when_current_and_fails_when_stale(self):
        files = {"index.html": HOME, "a.html": page("https://nemooperans.com/a", "{}")}
        with tempfile.TemporaryDirectory() as d:
            for n, b in files.items():
                open(os.path.join(d, n), "w").write(b)
            run = lambda *a: subprocess.run([sys.executable, TOOL, d, *a], capture_output=True, text=True, cwd=d)
            self.assertEqual(run().returncode, 0)
            self.assertEqual(run("--check").returncode, 0)
            open(os.path.join(d, "c.html"), "w").write(page("https://nemooperans.com/c", "{not json"))
            r = run("--check")
            self.assertEqual(r.returncode, 1)
            self.assertIn("WARNING: c.html", r.stdout)

    def test_check_fails_when_lastmod_deleted_or_old_and_on_unknown_flag(self):
        with tempfile.TemporaryDirectory() as d:
            for n, b in {"index.html": HOME, "a.html": page("https://nemooperans.com/a", '{"mainEntity":{"datePublished":"2026-03-01"}}')}.items():
                open(os.path.join(d, n), "w").write(b)
            run = lambda *a: subprocess.run([sys.executable, TOOL, d, *a], capture_output=True, text=True, cwd=d)
            run()
            sm = os.path.join(d, "sitemap.xml")
            good = open(sm).read()
            import re
            open(sm, "w").write(re.sub(r"\s*<lastmod>[^<]*</lastmod>", "", good))
            r = run("--check")
            self.assertEqual(r.returncode, 1)
            self.assertIn("missing <lastmod>", r.stderr)
            open(sm, "w").write(re.sub(r"<lastmod>[^<]*</lastmod>", "<lastmod>2020-01-01</lastmod>", good))
            self.assertEqual(run("--check").returncode, 1)
            self.assertEqual(run("--chek").returncode, 2)


if __name__ == "__main__":
    unittest.main()
