"""apply_topics must write only on an explicit --write; anything else is refused before any write."""
import hashlib, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOOL = ROOT / 'tools' / 'apply_topics.py'
INDEX = ROOT / 'index.html'


def test_unknown_or_missing_arg_refused_and_writes_nothing():
    before = hashlib.sha256(INDEX.read_bytes()).hexdigest()
    for args in ([], ['--help'], ['--chek'], ['--check', '--write']):
        r = subprocess.run([sys.executable, '-I', str(TOOL), *args], capture_output=True, text=True)
        assert r.returncode == 2, (args, r.returncode, r.stdout, r.stderr)
        assert 'wrote index.html' not in r.stdout
    assert hashlib.sha256(INDEX.read_bytes()).hexdigest() == before
