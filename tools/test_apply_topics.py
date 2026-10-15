"""apply_topics must write only on an explicit --write; anything else is refused before any write.

Run: python3 -m unittest discover -s tools
"""
import hashlib, pathlib, subprocess, sys, unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOOL = ROOT / 'tools' / 'apply_topics.py'
INDEX = ROOT / 'index.html'


class ApplyTopicsTests(unittest.TestCase):
    def test_unknown_or_missing_arg_refused_and_writes_nothing(self):
        before = hashlib.sha256(INDEX.read_bytes()).hexdigest()
        for args in ([], ['--help'], ['--chek'], ['--check', '--write']):
            r = subprocess.run([sys.executable, '-I', str(TOOL), *args], capture_output=True, text=True)
            self.assertEqual(r.returncode, 2, (args, r.returncode, r.stdout, r.stderr))
            self.assertNotIn('wrote index.html', r.stdout)
        self.assertEqual(hashlib.sha256(INDEX.read_bytes()).hexdigest(), before)


if __name__ == '__main__':
    unittest.main()