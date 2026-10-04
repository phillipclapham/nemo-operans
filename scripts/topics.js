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

  function fromHash() {
    let h = location.hash.slice(1);
    try { h = decodeURIComponent(h); } catch (e) { /* malformed escape: use as is */ }
    return h.toLowerCase();
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

  // Only topic hashes drive the filter; any other in-page anchor leaves it alone.
  window.addEventListener('hashchange', () => {
    const t = fromHash();
    if (known.has(t)) apply(t);
  });

  nav.hidden = false;
  const initial = fromHash();
  if (location.hash && !known.has(initial)) {
    if (!document.getElementById(location.hash.slice(1))) setHash('');
    apply('');
  } else {
    apply(initial);
  }
})();
