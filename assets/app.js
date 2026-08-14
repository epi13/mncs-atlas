const toggle = document.querySelector('.nav-toggle');
const nav = document.querySelector('#site-nav');

function closeNav() {
  if (!toggle || !nav) return;
  nav.classList.remove('open');
  toggle.setAttribute('aria-expanded', 'false');
}

if (toggle && nav) {
  toggle.addEventListener('click', () => {
    const open = nav.classList.toggle('open');
    toggle.setAttribute('aria-expanded', String(open));
  });

  nav.addEventListener('click', (event) => {
    if (event.target instanceof HTMLAnchorElement) closeNav();
  });

  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && nav.classList.contains('open')) {
      closeNav();
      toggle.focus();
    }
  });

  window.addEventListener('resize', () => {
    if (window.innerWidth > 820) closeNav();
  });
}

const year = document.querySelector('#year');
if (year) year.textContent = String(new Date().getFullYear());
