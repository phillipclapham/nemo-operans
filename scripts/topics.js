/**
 * Topic filter - Nemo Operans index
 *
 * Chips live in nav.topic-filter (hidden until this runs, so no-JS readers see the full list).
 * Each card carries data-topics="a b". The active topic is mirrored in the URL hash (#memory)
 * so a filtered view can be linked. Markup comes from tools/apply_topics.py; counts are
 * recomputed here from the live list so a card added after the last run is still counted.
 */
(function() {
  const nav = document.querySelector('.topic-filter');
  if (!nav) return;
  const status = document.querySelector('.topic-status');
  const chips = Array.from(nav.querySelectorAll('.topic-chip'));
  const cards = Array.from(document.querySelectorAll('.essay-list .essay-card'));
  const topicsOf = card => (card.dataset.topics || '').split(' ').filter(Boolean);
  const known = new Set(chips.map(c => c.dataset.topic).filter(Boolean));

  chips.forEach(chip => {
    const topic = chip.dataset.topic;
    const n = topic ? cards.filter(c => topicsOf(c).includes(topic)).length : cards.length;
    const count = chip.querySelector('.topic-count');
    if (count) count.textContent = n;
  });

  function rawHash() {
    const h = location.hash.slice(1);
    try { return decodeURIComponent(h); } catch (e) { return h; }
  }

  function apply(topic) {
    chips.forEach(c => c.setAttribute('aria-pressed', String(c.dataset.topic === topic)));
    let shown = 0;
    cards.forEach(card => {
      card.hidden = topic !== '' && !topicsOf(card).includes(topic);
      if (!card.hidden) shown++;
    });
    if (status) status.textContent = shown + (shown === 1 ? ' essay' : ' essays');
  }

  function setHash(topic) {
    history.replaceState(null, '', topic ? '#' + topic : location.pathname + location.search);
  }

  nav.addEventListener('click', e => {
    const chip = e.target.closest('.topic-chip');
    if (!chip) return;
    setHash(chip.dataset.topic);
    apply(chip.dataset.topic);
  });

  // One path for page load and hash changes: empty = All, a topic = filter, a real in-page
  // anchor leaves the filter alone, anything else falls back to All and clears the hash.
  function sync() {
    const raw = rawHash();
    const topic = raw.toLowerCase();
    if (raw === '') return apply('');
    if (known.has(topic)) return apply(topic);
    if (document.getElementById(raw)) return;
    setHash('');
    apply('');
  }

  window.addEventListener('hashchange', sync);

  nav.hidden = false;
  apply('');
  sync();
})();
