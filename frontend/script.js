/* ============================================================
   TradeWise — Landing Page Script
   ============================================================ */

(function () {
  'use strict';

  /* ===== HAMBURGER MENU ===== */
  var hamburger = document.getElementById('hamburger');
  var navLinks  = document.getElementById('navLinks');

  if (hamburger && navLinks) {
    hamburger.addEventListener('click', function () {
      var open = navLinks.classList.toggle('open');
      hamburger.classList.toggle('open', open);
      hamburger.setAttribute('aria-expanded', open);
    });

    // Close menu when a nav link is clicked
    navLinks.querySelectorAll('a').forEach(function (link) {
      link.addEventListener('click', function () {
        navLinks.classList.remove('open');
        hamburger.classList.remove('open');
        hamburger.setAttribute('aria-expanded', false);
      });
    });
  }

  /* ===== STICKY NAVBAR ===== */
  var navbar = document.getElementById('navbar');
  if (navbar) {
    function handleScroll() {
      if (window.scrollY > 50) {
        navbar.classList.add('scrolled');
      } else {
        navbar.classList.remove('scrolled');
      }
    }
    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();
  }

  /* ===== FADE-IN ON SCROLL ===== */
  var fadeEls = document.querySelectorAll('.fade-in');
  if (fadeEls.length && 'IntersectionObserver' in window) {
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.15, rootMargin: '0px 0px -40px 0px' });

    fadeEls.forEach(function (el) { observer.observe(el); });
  } else {
    // Fallback: show all elements if IntersectionObserver not supported
    fadeEls.forEach(function (el) { el.classList.add('visible'); });
  }

  /* ===== COUNTER ANIMATION ===== */
  function animateCounter(el, target, duration) {
    var startTime = null;
    var startVal  = 0;

    function step(timestamp) {
      if (!startTime) startTime = timestamp;
      var progress = Math.min((timestamp - startTime) / duration, 1);
      // Ease-out
      var eased = 1 - Math.pow(1 - progress, 3);
      el.textContent = Math.floor(startVal + eased * (target - startVal)).toLocaleString();
      if (progress < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  var counterEls = document.querySelectorAll('[data-target]');
  if (counterEls.length && 'IntersectionObserver' in window) {
    var counterObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          var el     = entry.target;
          var target = parseInt(el.getAttribute('data-target'), 10);
          if (!isNaN(target)) animateCounter(el, target, 1800);
          counterObserver.unobserve(el);
        }
      });
    }, { threshold: 0.5 });

    counterEls.forEach(function (el) { counterObserver.observe(el); });
  } else {
    // Fallback: just set the number
    counterEls.forEach(function (el) {
      var target = parseInt(el.getAttribute('data-target'), 10);
      if (!isNaN(target)) el.textContent = target.toLocaleString();
    });
  }

  /* ===== SMOOTH SCROLL FOR ANCHOR LINKS ===== */
  document.querySelectorAll('a[href^="#"]').forEach(function (anchor) {
    anchor.addEventListener('click', function (e) {
      var id = this.getAttribute('href').slice(1);
      if (!id) return;
      var target = document.getElementById(id);
      if (target) {
        e.preventDefault();
        var navH = navbar ? navbar.offsetHeight : 0;
        var top  = target.getBoundingClientRect().top + window.pageYOffset - navH - 16;
        window.scrollTo({ top: top, behavior: 'smooth' });
      }
    });
  });

})();
