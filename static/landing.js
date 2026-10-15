const header = document.querySelector('.site-header');
const menu = document.querySelector('.menu-toggle');
header.classList.add('enhanced');
menu.addEventListener('click', () => {
 const open = header.classList.toggle('open');
 menu.setAttribute('aria-expanded', String(open));
});
document.querySelectorAll('#main-nav a').forEach(link => link.addEventListener('click', () => {
 header.classList.remove('open'); menu.setAttribute('aria-expanded','false');
}));
document.addEventListener('keydown', event => {
 if (event.key === 'Escape' && header.classList.contains('open')) {
  header.classList.remove('open'); menu.setAttribute('aria-expanded','false'); menu.focus();
 }
});

document.querySelectorAll('[data-view]').forEach(button => {
 button.addEventListener('click', () => {
  document.querySelectorAll('[data-view]').forEach(other => other.setAttribute('aria-pressed', String(other === button)));
  document.querySelectorAll('.experience-panel').forEach(panel => { panel.hidden = panel.id !== button.getAttribute('aria-controls'); });
 });
});
if ('IntersectionObserver' in window && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
 const observer = new IntersectionObserver(entries => {
  entries.forEach(entry => { if (entry.isIntersecting) { entry.target.classList.add('scroll-reveal'); observer.unobserve(entry.target); } });
 }, {threshold: .15});
 document.querySelectorAll('.feature-card,.plan,.mission-art').forEach(element => observer.observe(element));
}

// Mission illustration: draw the road, then a patient walks the care journey —
// the check pops as it passes, the next step pulses on arrival, and it loops.
(() => {
  const art = document.querySelector('[data-journey-art]');
  if (!art || !('IntersectionObserver' in window) || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const path = art.querySelector('[data-journey-path]');
  const walker = art.querySelector('[data-journey-walker]');
  const stops = [...art.querySelectorAll('[data-journey-stop]')];
  if (!path || !walker || typeof path.getTotalLength !== 'function') return;
  art.classList.add('ja-ready');
  const total = path.getTotalLength();
  // Where along the path each stop sits (closest sampled point).
  const at = stops.map((el) => {
    const [x, y] = el.dataset.journeyStop.split(',').map(Number);
    let best = 0, dist = Infinity;
    for (let l = 0; l <= total; l += 2) { const p = path.getPointAtLength(l); const d = (p.x - x) ** 2 + (p.y - y) ** 2; if (d < dist) { dist = d; best = l; } }
    return best;
  });
  const start = total * 0.04, end = at[at.length - 1] + 6;
  const travel = 5200, rest = 1600;
  let running = false, raf = 0, t0 = 0, hits = new Set();
  const ease = (t) => (t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2);
  const pop = (el) => { el.classList.remove('hit'); void el.getBoundingClientRect(); el.classList.add('hit', 'done'); };
  const frame = (now) => {
    if (!running) return;
    const elapsed = (now - t0) % (travel + rest);
    if (elapsed < travel) {
      const len = start + (end - start) * ease(elapsed / travel);
      const p = path.getPointAtLength(len);
      walker.setAttribute('transform', `translate(${p.x} ${p.y})`);
      const arrived = hits.has(at.length - 1);
      walker.classList.toggle('on', !arrived);
      at.forEach((l, i) => { if (len >= l - 4 && !hits.has(i)) { hits.add(i); pop(stops[i]); } });
    } else {
      walker.classList.remove('on');
      if (hits.size) hits = new Set();
    }
    raf = requestAnimationFrame(frame);
  };
  let started = false;
  new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        art.classList.add('ja-live');
        if (!running) {
          running = true;
          setTimeout(() => { t0 = performance.now(); raf = requestAnimationFrame(frame); }, started ? 0 : 1700);
          started = true;
        }
      } else if (running) { running = false; cancelAnimationFrame(raf); walker.classList.remove('on'); hits = new Set(); }
    });
  }, { threshold: 0.35 }).observe(art);
})();
