(() => {
  const input = document.querySelector('#blog-search');
  const cards = [...document.querySelectorAll('.blog-card')];
  const empty = document.querySelector('#no-results');
  if (input && cards.length) {
    input.addEventListener('input', () => {
      const query = input.value.trim().toLocaleLowerCase('tr-TR');
      let visible = 0;
      cards.forEach(card => {
        const show = !query || card.dataset.search.toLocaleLowerCase('tr-TR').includes(query);
        card.hidden = !show;
        if (show) visible += 1;
      });
      if (empty) empty.hidden = visible !== 0;
    });
  }

  const links = [...document.querySelectorAll('.toc a')];
  if (!links.length || !('IntersectionObserver' in window)) return;
  const byId = new Map(links.map(link => [link.hash.slice(1), link]));
  const headings = [...document.querySelectorAll('.prose h2[id]')];
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      links.forEach(link => link.classList.remove('active'));
      byId.get(entry.target.id)?.classList.add('active');
    });
  }, { rootMargin: '-15% 0px -70% 0px' });
  headings.forEach(heading => observer.observe(heading));
})();
