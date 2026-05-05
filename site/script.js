'use strict';

// ── Theme toggle ────────────────────────────────────────────────────────────
const html = document.documentElement;
const themeBtn = document.getElementById('themeToggle');

function applyTheme(theme) {
  html.setAttribute('data-theme', theme);
  localStorage.setItem('theme', theme);
}

(function initTheme() {
  const saved = localStorage.getItem('theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  applyTheme(saved || (prefersDark ? 'dark' : 'light'));
})();

themeBtn.addEventListener('click', () => {
  applyTheme(html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark');
});

// ── Scroll animations ────────────────────────────────────────────────────────
const observer = new IntersectionObserver(
  (entries) => entries.forEach(e => { if (e.isIntersecting) { e.target.classList.add('visible'); observer.unobserve(e.target); } }),
  { threshold: 0.12 }
);
document.querySelectorAll('.animate-on-scroll').forEach(el => observer.observe(el));

// ── Burger menu ──────────────────────────────────────────────────────────────
const burger = document.getElementById('burger');
const nav    = document.getElementById('nav');
const navLinks = document.getElementById('navLinks');

burger.addEventListener('click', () => {
  const open = nav.classList.toggle('nav--open');
  burger.setAttribute('aria-expanded', String(open));
});

navLinks.querySelectorAll('a').forEach(link =>
  link.addEventListener('click', () => {
    nav.classList.remove('nav--open');
    burger.setAttribute('aria-expanded', 'false');
  })
);

// ── Footer year ──────────────────────────────────────────────────────────────
const yearEl = document.getElementById('year');
if (yearEl) yearEl.textContent = new Date().getFullYear();
