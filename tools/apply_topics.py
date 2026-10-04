#!/usr/bin/env python3
"""Apply tools/topics.json to index.html: per-card data-topics + data-noted, the topic chip row
and the "Start here" featured card. Idempotent; run after every publish.

- data-noted is DERIVED from each essay page (it carries a correction-note blockquote), never stored.
- Validates everything BEFORE writing: unknown slugs or topic ids, a card with no topics (a new
  essay published without a topics.json entry), a missing essay page, broken block markers.
  Any failure exits 1 and writes nothing.
- Only the tool-owned attributes (data-topics, data-noted) are rewritten on a card: the opening tag
  is parsed (html.parser), those two are dropped by exact name, and the tag is rebuilt double-quoted.
- Chip counts are written for no-JS readers; scripts/topics.js recounts from the live list.
Usage: python3 tools/apply_topics.py [--check]   (--check: validate and report, write nothing)
"""
import html, json, pathlib, re, sys
from html.parser import HTMLParser

ROOT = pathlib.Path(__file__).resolve().parent.parent
INDEX = ROOT / 'index.html'


def fail(msg):
    print(f'apply_topics: {msg}', file=sys.stderr)
    sys.exit(1)


cfg = json.loads((ROOT / 'tools' / 'topics.json').read_text())
topic_ids = [t['id'] for t in cfg['topics']]
s = INDEX.read_text()

CARD = re.compile(r'<a href="/([^"]+)" class="essay-card"[^>]*>')
cards = CARD.findall(s)

# ---- validate first; nothing is written unless every check passes ----
if len(set(cards)) != len(cards):
    fail(f'duplicate cards: {sorted({c for c in cards if cards.count(c) > 1})}')
unknown = [slug for slug in cfg['essays'] if slug not in cards]
if unknown:
    fail(f'topics.json names slugs with no card: {unknown}')
if len(set(topic_ids)) != len(topic_ids):
    fail(f'duplicate topic ids: {topic_ids}')
badid = [t for t in topic_ids if not re.fullmatch(r'[a-z0-9-]+', t)]
if badid:
    fail(f'topic ids must be lowercase slugs (they become URL hashes): {badid}')
bad = [(slug, t) for slug, ts in cfg['essays'].items() for t in ts if t not in topic_ids]
if bad:
    fail(f'unknown topic ids: {bad}')
untagged = [c for c in cards if not cfg['essays'].get(c)]
if untagged:
    fail('cards with no topics (add them to tools/topics.json): ' + ', '.join(untagged))
missing = [c for c in cards if not (ROOT / f'{c}.html').exists()]
if missing:
    fail(f'cards with no essay page: {missing}')
if cfg['featured'] not in cards:
    fail(f'featured slug has no card: {cfg["featured"]}')

noted = {c for c in cards if 'class="correction-note"' in (ROOT / f'{c}.html').read_text()}


class _TagAttrs(HTMLParser):
    """Parse one start tag into (name, value) pairs; quoted values are never mistaken for attributes."""
    def handle_starttag(self, tag, attrs):
        self.attrs = attrs


OWNED = {'data-topics', 'data-noted'}


def card_tag(m):
    slug = m.group(1)
    p = _TagAttrs()
    p.feed(m.group(0))
    attrs = [(k, v) for k, v in p.attrs if k not in OWNED]   # html.parser lowercases names
    attrs.append(('data-topics', ' '.join(cfg['essays'][slug])))
    if slug in noted:
        attrs.append(('data-noted', None))
    parts = [k if v is None else f'{k}="{html.escape(v, quote=True)}"' for k, v in attrs]
    return '<a ' + ' '.join(parts) + '>'


s = CARD.sub(card_tag, s)
for slug in cards:
    t = re.search(r'<a href="/' + re.escape(slug) + r'" class="essay-card"[^>]*>', s).group(0)
    p = _TagAttrs()
    p.feed(t)
    names = [k for k, _ in p.attrs]
    if names.count('data-topics') != 1 or names.count('data-noted') != (slug in noted):
        fail(f'card attributes did not normalize: {t}')

# featured card, built from the listed card's own fields, bounded to that one card element
card_m = re.search(r'<a href="/' + re.escape(cfg['featured']) + r'" class="essay-card"[^>]*>(.*?)</a>', s, re.S)
fields = {}
for name, pat in (('title', r'<h3 class="essay-card-title">(.*?)</h3>'),
                  ('subtitle', r'<p class="essay-card-subtitle">(.*?)</p>'),
                  ('meta', r'<span class="essay-card-meta">(.*?)</span>')):
    found = re.findall(pat, card_m.group(1), re.S)
    if len(found) != 1:
        fail(f'featured card needs exactly one {name}, found {len(found)}')
    fields[name] = found[0]
featured_html = (f'<a href="/{cfg["featured"]}" class="featured-card">\n'
                 f'  <span class="featured-label">Start here</span>\n'
                 f'  <h2 class="featured-title">{fields["title"]}</h2>\n'
                 f'  <p class="featured-subtitle">{fields["subtitle"]}</p>\n'
                 f'  <span class="featured-meta">{fields["meta"]}</span>\n'
                 f'</a>')

counts = {t: sum(t in ts for ts in cfg['essays'].values()) for t in topic_ids}
chips = ['<nav class="topic-filter" aria-label="Filter essays by topic" hidden>',
         f'  <button type="button" class="topic-chip" data-topic="" aria-pressed="true">All <span class="topic-count">{len(cards)}</span></button>']
for t in cfg['topics']:
    chips.append(f'  <button type="button" class="topic-chip" data-topic="{t["id"]}" aria-pressed="false">'
                 f'{html.escape(t["label"])} <span class="topic-count">{counts[t["id"]]}</span></button>')
chips += ['</nav>', '<p class="topic-status" aria-live="polite"></p>']
chip_html = '\n'.join(chips)


def put(name, text, anchor_before):
    global s
    start, end = f'<!-- topics:{name}:start -->', f'<!-- topics:{name}:end -->'
    ns, ne = s.count(start), s.count(end)
    body = f'{start}\n{text}\n{end}'
    if ns == 0 and ne == 0:
        if s.count(anchor_before) != 1:
            fail(f'anchor must appear exactly once: {anchor_before}')
        s = s.replace(anchor_before, body + '\n' + anchor_before)
    elif ns == 1 and ne == 1 and s.index(start) < s.index(end):
        s, n = re.subn(re.escape(start) + r'.*?' + re.escape(end), lambda _: body, s, count=1, flags=re.S)
        if n != 1:
            fail(f'could not replace the {name} block')
    else:
        fail(f'{name} markers are broken ({ns} start, {ne} end); fix index.html by hand')


put('featured', featured_html, '<h2 class="section-title">Essays</h2>')
put('chips', chip_html, '<div class="essay-list">')
if 'scripts/topics.js' not in s:
    if s.count('<script src="scripts/theme.js"></script>') != 1:
        fail('theme.js script tag not found exactly once')
    s = s.replace('<script src="scripts/theme.js"></script>',
                  '<script src="scripts/theme.js"></script>\n    <script src="scripts/topics.js" defer></script>')

print(f'{len(cards)} cards · counts {counts} · noted {len(noted)}')
if '--check' not in sys.argv:
    INDEX.write_text(s)
    print('wrote index.html')
