/**
 * Topic filter - Nemo Operans index
 *
 * Chips live in nav.topic-filter (hidden until this runs, so no-JS readers see the full list).
 * Each card carries data-topics="a b". The active topic is mirrored in the URL hash (#memory)
 * so a filtered view can be linked. Markup and counts come from tools/apply_topics.py.
 */
(function() {
  const nav = document.querySelector('.topic-filter');
  if (!nav) return;
  const chips = Array.from(nav.querySelectorAll('.topic-chip'));
  const cards = Array.from(document.querySelectorAll('.essay-list .essay-card'));
  const known = new Set(chips.map(c => c.dataset.topic).filter(Boolean));

  function apply(topic) {
    if (!known.has(topic)) topic = '';
    chips.forEach(c => c.setAttribute('aria-pressed', String(c.dataset.topic === topic)));
    cards.forEach(card => {
      const topics = (card.dataset.topics || '').split(' ');
      card.hidden = topic !== '' && !topics.includes(topic);
    });
  }

  nav.addEventListener('click', e => {
    const chip = e.target.closest('.topic-chip');
    if (!chip) return;
    const topic = chip.dataset.topic;
    history.replaceState(null, '', topic ? '#' + topic : location.pathname + location.search);
    apply(topic);
  });

  window.addEventListener('hashchange', () => apply(location.hash.slice(1)));

  nav.hidden = false;
  apply(location.hash.slice(1));
})();
