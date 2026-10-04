#!/usr/bin/env python3
"""Apply tools/topics.json to index.html: per-card data-topics + data-noted, the topic chip row
(with counts) and the "Start here" featured card. Idempotent; re-run after every publish.

- data-noted is DERIVED from each essay page (it carries a correction-note blockquote), never stored.
- Refuses a topics.json slug with no card, and an unknown topic id. Lists cards with no topics
  (a new essay published without an entry) and exits 1 so it can't go unnoticed.
Usage: python3 tools/apply_topics.py [--check]   (--check: report only, write nothing)
"""
import html, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
INDEX = ROOT / 'index.html'
cfg = json.loads((ROOT / 'tools' / 'topics.json').read_text())
topic_ids = [t['id'] for t in cfg['topics']]
s = INDEX.read_text()

CARD = re.compile(r'<a href="/([^"]+)" class="essay-card"[^>]*>')
cards = CARD.findall(s)
unknown = [slug for slug in cfg['essays'] if slug not in cards]
bad = [(slug, t) for slug, ts in cfg['essays'].items() for t in ts if t not in topic_ids]
assert not unknown, f'topics.json names slugs with no card: {unknown}'
assert not bad, f'unknown topic ids: {bad}'
assert cfg['featured'] in cards, 'featured slug has no card'

def card_attrs(m):
    slug = m.group(1)
    tag = re.search(r'data-tags="([^"]*)"', m.group(0))
    attrs = [f'href="/{slug}"', 'class="essay-card"']
    if tag:
        attrs.append(f'data-tags="{tag.group(1)}"')
    attrs.append(f'data-topics="{" ".join(cfg["essays"].get(slug, []))}"')
    if 'class="correction-note"' in (ROOT / f'{slug}.html').read_text():
        attrs.append('data-noted')
    return '<a ' + ' '.join(attrs) + '>'

s = CARD.sub(card_attrs, s)

# chip row, counts derived from the map
counts = {t: sum(t in ts for ts in cfg['essays'].values()) for t in topic_ids}
chips = ['<nav class="topic-filter" aria-label="Filter essays by topic" hidden>',
         f'  <button type="button" class="topic-chip" data-topic="" aria-pressed="true">All <span class="topic-count">{len(cards)}</span></button>']
for t in cfg['topics']:
    chips.append(f'  <button type="button" class="topic-chip" data-topic="{t["id"]}" aria-pressed="false">'
                 f'{html.escape(t["label"])} <span class="topic-count">{counts[t["id"]]}</span></button>')
chips.append('</nav>')
chip_html = '\n'.join(chips)

# featured card, built from the listed card's own title/subtitle/meta
fm = re.search(r'<a href="/' + re.escape(cfg['featured']) + r'"[^>]*>.*?essay-card-title">(.*?)</h3>\s*'
               r'<p class="essay-card-subtitle">(.*?)</p>\s*<span class="essay-card-meta">(.*?)</span>', s, re.S)
featured_html = (f'<a href="/{cfg["featured"]}" class="featured-card">\n'
                 f'  <span class="featured-label">Start here</span>\n'
                 f'  <h3 class="featured-title">{fm.group(1)}</h3>\n'
                 f'  <p class="featured-subtitle">{fm.group(2)}</p>\n'
                 f'  <span class="featured-meta">{fm.group(3)}</span>\n'
                 f'</a>')

def put(block, name, text, anchor_before):
    global s
    start, end = f'<!-- topics:{name}:start -->', f'<!-- topics:{name}:end -->'
    body = f'{start}\n{text}\n{end}'
    if start in s:
        s = re.sub(re.escape(start) + r'.*?' + re.escape(end), lambda _: body, s, flags=re.S)
    else:
        assert s.count(anchor_before) == 1, f'anchor not unique: {anchor_before}'
        s = s.replace(anchor_before, body + '\n' + anchor_before)

put('featured', 'featured', featured_html, '<h2 class="section-title">Essays</h2>')
put('chips', 'chips', chip_html, '<div class="essay-list">')
if 'scripts/topics.js' not in s:
    s = s.replace('<script src="scripts/theme.js"></script>',
                  '<script src="scripts/theme.js"></script>\n    <script src="scripts/topics.js" defer></script>')

untagged = [c for c in cards if not cfg['essays'].get(c)]
print(f'{len(cards)} cards · counts {counts} · noted {s.count(" data-noted>")}')
if '--check' not in sys.argv:
    INDEX.write_text(s)
    print('wrote index.html')
if untagged:
    print('UNTAGGED (add to tools/topics.json):', ', '.join(untagged))
    sys.exit(1)
