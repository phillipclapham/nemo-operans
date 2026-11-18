"""Run: python3 -m unittest discover -s tools"""
import datetime
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_sitemap as gs  # noqa: E402

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


# Every unit test below runs against this day, never the real clock, so none of them rots.
FIXED = datetime.date(2026, 12, 1)
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false"]


def commit(repo, day):
    """Commit everything in repo, authored and committed at noon on `day` (YYYY-MM-DD)."""
    env = dict(os.environ, GIT_AUTHOR_DATE=f"{day}T12:00:00", GIT_COMMITTER_DATE=f"{day}T12:00:00")
    subprocess.run([*GIT, "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run([*GIT, "commit", "-q", "-m", f"edit {day}"], cwd=repo, check=True,
                   capture_output=True, env=env)


def note_essay(stamp, text, body="Body."):
    dated = f" {stamp}" if stamp else ""
    return ('<html><head><meta property="og:url" content="https://nemooperans.com/essay"></head><body>\n'
            '<blockquote class="correction-note">\n'
            f'<p><strong>Correction note — October 4, 2026{dated}.</strong> {text}</p>\n'
            '</blockquote>\n'
            f'<p>{body}</p>\n</body></html>\n')


class CorrectionStampTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = self.tmp.name
        subprocess.run(["git", "init", "-q", self.repo], check=True)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, text, name="essay.html"):
        with open(os.path.join(self.repo, name), "w", encoding="utf-8") as f:
            f.write(text)

    def problems(self, today=FIXED):
        return gs.stamp_problems(self.repo, ["essay.html"], today=today)

    def test_reproduced_cost_parity_shape_is_flagged(self):
        # Reproduced 2026-11-16: the note was reworded on 2026-11-15 and still said November 6.
        self.write(note_essay("(updated November 6, 2026)", "text A"))
        commit(self.repo, "2026-11-06")
        self.write(note_essay("(updated November 6, 2026)", "text B"))
        commit(self.repo, "2026-11-15")
        found = self.problems()
        self.assertEqual(len(found), 1, found)
        self.assertIn("stamped 2026-11-06", found[0])
        self.assertIn("last changed 2026-11-15", found[0])

    def test_restamping_to_the_text_change_date_passes(self):
        self.write(note_essay("(updated November 6, 2026)", "text A"))
        commit(self.repo, "2026-11-06")
        self.write(note_essay("(updated November 6, 2026)", "text B"))
        commit(self.repo, "2026-11-15")
        self.write(note_essay("(updated November 15, 2026)", "text B"))
        commit(self.repo, "2026-11-15")
        self.assertEqual(self.problems(), [])

    def test_body_edit_outside_the_note_does_not_move_the_date(self):
        self.write(note_essay("(updated November 5, 2026)", "text A"))
        commit(self.repo, "2026-11-05")
        self.write(note_essay("(updated November 5, 2026)", "text A", body="Body edited."))
        commit(self.repo, "2026-11-06")
        self.assertEqual(self.problems(), [])

    def test_restamp_the_day_after_a_text_change_passes(self):
        # Mirrors welcome-to-the-party-pal: text rewritten 11-07, restamp committed 11-08.
        self.write(note_essay("(updated October 29, 2026)", "text A"))
        commit(self.repo, "2026-10-29")
        self.write(note_essay("(updated October 29, 2026)", "text B"))
        commit(self.repo, "2026-11-07")
        self.assertEqual(len(self.problems()), 1)
        self.write(note_essay("(updated November 7, 2026)", "text B"))
        commit(self.repo, "2026-11-08")
        self.assertEqual(self.problems(), [])

    def test_uncommitted_note_edit_needs_todays_stamp(self):
        self.write(note_essay("(updated November 5, 2026)", "text A"))
        commit(self.repo, "2026-11-05")
        self.write(note_essay("(updated November 5, 2026)", "text B"))
        found = self.problems()
        self.assertEqual(len(found), 1, found)
        self.assertIn(f"last changed {FIXED.isoformat()}", found[0])
        self.write(note_essay("(updated December 1, 2026)", "text B"))
        self.assertEqual(self.problems(), [])

    def test_note_without_a_stamp_is_not_checked(self):
        self.write(note_essay("", "text A"))
        commit(self.repo, "2026-11-05")
        self.write(note_essay("", "text B"))
        commit(self.repo, "2026-11-15")
        self.assertEqual(self.problems(), [])

    def test_revised_stamp_is_checked_like_updated(self):
        self.write(note_essay("(revised October 5, 2026)", "text A"))
        commit(self.repo, "2026-10-05")
        self.write(note_essay("(revised October 5, 2026)", "text B"))
        commit(self.repo, "2026-10-29")
        found = self.problems()
        self.assertEqual(len(found), 1, found)
        self.assertIn("stamped 2026-10-05", found[0])
        self.assertIn("last changed 2026-10-29", found[0])

    def test_unreadable_stamp_in_a_note_header_is_reported(self):
        self.write(note_essay("(updated 6 November 2026)", "text A"))
        commit(self.repo, "2026-11-06")
        found = self.problems()
        self.assertEqual(len(found), 1, found)
        self.assertIn("unreadable", found[0])
        self.assertIn("(updated 6 November 2026)", found[0])
        # Both keywords are accepted by the check, so the hint names both.
        self.assertIn("(revised <Month D, YYYY>)", found[0])

    def test_unreadable_stamp_beside_a_readable_one_in_one_header_is_reported(self):
        # Reproduced 2026-11-17 (Diogenes LOW, f61e387): the guard tested the whole header, so a
        # readable stamp in it hid an unreadable one beside it. Either order is reported once.
        # The message names the bad stamp and says it is unreadable; it must not claim that no
        # readable stamp exists, because the header holds one.
        cases = [
            ("(revised November 6, 2026) (updated 6 Nov 2026)", 1, "(updated 6 Nov 2026)"),
            ("(updated 6 Nov 2026) (revised November 6, 2026)", 1, "(updated 6 Nov 2026)"),
            ("(revised November 6, 2026) (updated November 6, 2026)", 0, None),
        ]
        for index, (header, expected, bad) in enumerate(cases):
            with self.subTest(header=header):
                self.write(note_essay(header, f"text {index}"))
                commit(self.repo, "2026-11-06")
                found = self.problems()
                self.assertEqual(len(found), expected, found)
                if expected:
                    self.assertIn("unreadable", found[0])
                    self.assertIn(bad, found[0])
                    self.assertNotIn("no readable", found[0])

    def test_word_updated_in_the_note_body_is_not_a_stamp_problem(self):
        self.write(note_essay("(updated November 6, 2026)", "Section 5 was updated in place."))
        commit(self.repo, "2026-11-06")
        self.assertEqual(self.problems(), [])

    def test_stamp_after_today_is_reported(self):
        self.write(note_essay("(updated December 3, 2026)", "text A"))
        commit(self.repo, "2026-11-06")
        found = self.problems()
        self.assertEqual(len(found), 1, found)
        self.assertIn("after today", found[0])

    def test_stamp_one_day_ahead_of_today_is_tolerated(self):
        self.write(note_essay("(updated December 2, 2026)", "text A"))
        commit(self.repo, "2026-11-06")
        self.assertEqual(self.problems(), [])

    def test_impossible_date_is_reported(self):
        self.write(note_essay("(updated February 30, 2026)", "text A"))
        commit(self.repo, "2026-11-06")
        found = self.problems()
        self.assertEqual(len(found), 1, found)
        self.assertIn("is not a date", found[0])

    def test_each_note_in_a_file_is_dated_on_its_own_text(self):
        # The first note is untouched since 10-29; the second is rewritten on 11-15. The
        # second's change must not drag the first's stamp into a finding.
        def two_notes(second_stamp, second_text):
            return ('<html><body>\n'
                    '<blockquote class="correction-note">\n'
                    '<p><strong>Correction note — October 4, 2026 (updated October 29, 2026).</strong> first</p>\n'
                    '</blockquote>\n'
                    '<blockquote class="correction-note">\n'
                    f'<p><strong>Correction note — October 4, 2026 {second_stamp}.</strong> {second_text}</p>\n'
                    '</blockquote>\n</body></html>\n')

        self.write(two_notes("(updated October 29, 2026)", "second A"))
        commit(self.repo, "2026-10-29")
        self.write(two_notes("(updated October 29, 2026)", "second B"))
        commit(self.repo, "2026-11-15")
        found = self.problems()
        self.assertEqual(len(found), 1, found)
        self.assertIn("stamped 2026-10-29, but its text last changed 2026-11-15", found[0])
        self.write(two_notes("(updated November 15, 2026)", "second B"))
        commit(self.repo, "2026-11-15")
        self.assertEqual(self.problems(), [])

    def test_a_dated_addendum_does_not_move_the_stamp(self):
        def with_addendum(text):
            return ('<html><body>\n<blockquote class="correction-note">\n'
                    '<p><strong>Correction note — October 4, 2026 (revised October 5, 2026).</strong> core</p>\n'
                    f'<p><strong>Update — October 29, 2026.</strong> {text}</p>\n'
                    '</blockquote>\n</body></html>\n')

        self.write(with_addendum("addendum A"))
        commit(self.repo, "2026-10-05")
        self.write(with_addendum("addendum B"))
        commit(self.repo, "2026-11-15")
        self.assertEqual(self.problems(), [])

    def test_an_unlabelled_sign_off_counts_as_a_revision(self):
        def with_sign_off(sign_off):
            tail = '<p><em>&mdash; Phill</em></p>\n' if sign_off else ""
            return ('<html><body>\n<blockquote class="correction-note">\n'
                    '<p><strong>Correction note — October 4, 2026 (updated October 29, 2026).</strong> core</p>\n'
                    f'{tail}</blockquote>\n</body></html>\n')

        self.write(with_sign_off(False))
        commit(self.repo, "2026-10-29")
        self.write(with_sign_off(True))
        commit(self.repo, "2026-11-02")
        found = self.problems()
        self.assertEqual(len(found), 1, found)
        self.assertIn("last changed 2026-11-02", found[0])

    def test_a_stamp_added_later_does_not_move_the_date(self):
        # Reproduced 2026-11-16 on how-i-think-with-ai: the note was written 10-05 with no
        # stamp and stamped "revised October 5" on 10-07. The unstamped lead paragraph has a
        # date in its header, and reading it as an addendum made the note look new on 10-07.
        self.write(note_essay("", "text A"))
        commit(self.repo, "2026-10-05")
        self.write(note_essay("(revised October 5, 2026)", "text A"))
        commit(self.repo, "2026-10-07")
        self.assertEqual(self.problems(), [])

    def test_variant_markup_is_still_checked(self):
        for opening in ('<blockquote class="correction-note featured">',
                        '<blockquote id="n1" class="correction-note">'):
            with self.subTest(opening=opening):
                def essay(text):
                    return ('<html><body>\n' + opening + '\n'
                            '<p><strong>Correction note — October 4, 2026 (updated November 6, 2026).</strong> '
                            f'{text}</p>\n</blockquote>\n</body></html>\n')

                self.write(essay("text A"))
                commit(self.repo, "2026-11-06")
                self.write(essay("text B"))
                commit(self.repo, "2026-11-15")
                self.assertEqual(len(self.problems()), 1)

    def test_nested_tag_around_an_unreadable_stamp_is_reported(self):
        self.write('<html><body>\n<blockquote class="correction-note">\n'
                   '<p><strong>Correction note — October 4, 2026 <em>(updated 6 Nov 2026)</em>.</strong> text</p>\n'
                   '</blockquote>\n</body></html>\n')
        commit(self.repo, "2026-11-06")
        found = self.problems()
        self.assertEqual(len(found), 1, found)
        self.assertIn("unreadable", found[0])
        self.assertIn("(updated 6 Nov 2026)", found[0])

    def test_reformatting_the_stamp_does_not_move_the_date(self):
        self.write(note_essay("(updated 6 November 2026)", "text A"))
        commit(self.repo, "2026-11-06")
        self.write(note_essay("(updated November 6, 2026)", "text A"))
        commit(self.repo, "2026-11-20")
        self.assertEqual(self.problems(), [])

    def test_one_day_behind_is_tolerated_and_two_days_is_not(self):
        self.write(note_essay("(updated November 5, 2026)", "text A"))
        commit(self.repo, "2026-11-06")
        self.assertEqual(self.problems(), [])
        self.write(note_essay("(updated November 4, 2026)", "text A"))
        commit(self.repo, "2026-11-06")
        found = self.problems()
        self.assertEqual(len(found), 1, found)
        self.assertIn("stamped 2026-11-04", found[0])

    def test_a_stamp_in_body_prose_of_an_unstamped_note_is_not_checked(self):
        self.write(note_essay("", "see the note (updated October 1, 2026) for details"))
        commit(self.repo, "2026-11-06")
        self.assertEqual(self.problems(), [])

    def test_emphasised_updated_in_an_unstamped_note_body_is_not_a_stamp_problem(self):
        # deepseek, L3 fix round 1: every <strong> in a paragraph is read as header text, so a
        # bold "updated" in the prose of an unstamped note used to fail the check.
        self.write(note_essay("", "We <strong>updated</strong> section 5."))
        commit(self.repo, "2026-11-06")
        self.assertEqual(self.problems(), [])

    def test_an_addendum_headed_updated_is_still_an_addendum(self):
        def with_addendum(text):
            return ('<html><body>\n<blockquote class="correction-note">\n'
                    '<p><strong>Correction note — October 4, 2026 (revised October 5, 2026).</strong> core</p>\n'
                    f'<p><strong>Updated — October 29, 2026.</strong> {text}</p>\n'
                    '</blockquote>\n</body></html>\n')

        self.write(with_addendum("addendum A"))
        commit(self.repo, "2026-10-05")
        self.write(with_addendum("addendum B"))
        commit(self.repo, "2026-11-15")
        self.assertEqual(self.problems(), [])

    def test_parenthesised_updated_prose_in_the_body_is_note_text(self):
        # codex, L3 fix round 1: stripping every "(updated ...)" hid a body edit from the check.
        self.write(note_essay("(updated November 6, 2026)", "text (updated draft A)"))
        commit(self.repo, "2026-11-06")
        self.write(note_essay("(updated November 6, 2026)", "text (updated draft B)"))
        commit(self.repo, "2026-11-15")
        found = self.problems()
        self.assertEqual(len(found), 1, found)
        self.assertIn("last changed 2026-11-15", found[0])

    def test_a_truncated_stamp_is_reported_not_read_as_no_stamp(self):
        # codex and deepseek, L3 round 2: with no closing paren the note read as unstamped and
        # the check passed without looking at its date.
        self.write('<html><body>\n<blockquote class="correction-note">\n'
                   '<p><strong>Correction note — October 4, 2026 (updated November 6, 2026.</strong> text</p>\n'
                   '</blockquote>\n</body></html>\n')
        commit(self.repo, "2026-11-06")
        found = self.problems()
        self.assertEqual(len(found), 1, found)
        self.assertIn("unreadable", found[0])
        self.assertIn("(updated November 6, 2026", found[0])

    def test_a_bold_parenthetical_in_the_body_is_note_text_and_not_a_stamp_problem(self):
        # codex and complement, L3 round 2: only the leading <strong> run is the header.
        def essay(draft):
            return note_essay("(updated November 6, 2026)", f"prose <strong>(updated draft {draft})</strong> more")

        self.write(essay("A"))
        commit(self.repo, "2026-11-06")
        self.assertEqual(self.problems(), [])
        self.write(essay("B"))
        commit(self.repo, "2026-11-15")
        found = self.problems()
        self.assertEqual(len(found), 1, found)
        self.assertIn("last changed 2026-11-15", found[0])

    def test_a_header_split_across_adjacent_strongs_is_still_read(self):
        def essay(text):
            return ('<html><body>\n<blockquote class="correction-note">\n'
                    '<p><strong>Correction note — October 4, 2026</strong> <strong>(updated November 6, 2026).</strong> '
                    f'{text}</p>\n</blockquote>\n</body></html>\n')

        self.write(essay("text A"))
        commit(self.repo, "2026-11-06")
        self.write(essay("text B"))
        commit(self.repo, "2026-11-15")
        found = self.problems()
        self.assertEqual(len(found), 1, found)
        self.assertIn("stamped 2026-11-06", found[0])

    def test_check_command_fails_on_a_stale_stamp_and_passes_once_restamped(self):
        # The CI command end to end, on the real clock: sitemap regenerated and committed each
        # time, stamp left behind. Dates are relative to today so the test holds on any day.
        today = datetime.date.today()
        first, second = today - datetime.timedelta(days=10), today - datetime.timedelta(days=5)

        def stamp(day):
            return f"(updated {day:%B} {day.day}, {day.year})"

        def regenerate_and_commit(day):
            subprocess.run([sys.executable, TOOL, self.repo], check=True, capture_output=True)
            commit(self.repo, day.isoformat())

        def check():
            return subprocess.run([sys.executable, TOOL, self.repo, "--check"],
                                  capture_output=True, text=True)

        self.write(HOME, "index.html")
        self.write(note_essay(stamp(first), "text A"))
        commit(self.repo, first.isoformat())
        regenerate_and_commit(first)
        self.write(note_essay(stamp(first), "text B"))
        commit(self.repo, second.isoformat())
        regenerate_and_commit(second)
        r = check()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("STAMP:", r.stderr)
        self.assertIn("essay.html", r.stderr)
        self.write(note_essay(stamp(second), "text B"))
        commit(self.repo, second.isoformat())
        subprocess.run([sys.executable, TOOL, self.repo], check=True, capture_output=True)
        r = check()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("sitemap.xml is current", r.stdout)

    def test_generation_warns_on_a_stale_stamp_outside_git(self):
        # No history: the note counts as changed today, so an old stamp is a warning, not a crash.
        r, _ = run_in({"index.html": HOME, "essay.html": note_essay("(updated October 4, 2026)", "text A")})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("WARNING: stamp: essay.html", r.stdout)


if __name__ == "__main__":
    unittest.main()
