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
