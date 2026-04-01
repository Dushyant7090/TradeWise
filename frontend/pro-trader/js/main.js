/**
 * main.js — App initialization, routing, and global UI components
 */

import Storage from './storage.js';
import Auth from './auth.js';
import Realtime from './realtime.js';
import { notificationsAPI } from './api.js';
import { timeAgo } from './utils.js';

// ===== CONFIG (injected from .env or window globals) =====
const SUPABASE_URL = window.TW_SUPABASE_URL || '';
const SUPABASE_ANON_KEY = window.TW_SUPABASE_ANON_KEY || '';

// ===== TOAST SYSTEM =====
const Toast = {
  container: null,

  init() {
    this.container = document.getElementById('toast-container');
    if (!this.container) {
      this.container = document.createElement('div');
      this.container.id = 'toast-container';
      this.container.className = 'toast-container';
      document.body.appendChild(this.container);
    }
    window.Toast = this; // Make globally accessible
  },

  show(message, type = 'info', duration = 4000) {
    const icons = {
      success: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>`,
      error: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>`,
      warning: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>`,
      info: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>`,
    };

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
      <div class="toast-icon">${icons[type] || icons.info}</div>
      <div class="toast-content">
        <div class="toast-message">${message}</div>
      </div>
      <button class="toast-dismiss" aria-label="Dismiss">×</button>
    `;

    this.container.appendChild(toast);
    requestAnimationFrame(() => toast.classList.add('show'));

    const dismiss = () => {
      toast.classList.remove('show');
      setTimeout(() => toast.remove(), 350);
    };

    toast.querySelector('.toast-dismiss').addEventListener('click', dismiss);
    if (duration > 0) setTimeout(dismiss, duration);

    return toast;
  },
};

// ===== SIDEBAR NAVIGATION =====
const Sidebar = {
  init() {
    const hamburger = document.getElementById('hamburger');
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');

    if (!hamburger || !sidebar) return;

    hamburger.addEventListener('click', () => this.toggle(sidebar, overlay));
    overlay?.addEventListener('click', () => this.close(sidebar, overlay));

    // Mark active link
    this.setActiveLink();
  },

  toggle(sidebar, overlay) {
    const isOpen = sidebar.classList.contains('open');
    isOpen ? this.close(sidebar, overlay) : this.open(sidebar, overlay);
  },

  open(sidebar, overlay) {
    sidebar.classList.add('open');
    overlay?.classList.add('active');
    document.body.style.overflow = 'hidden';
    const hamburger = document.getElementById('hamburger');
    if (hamburger) hamburger.setAttribute('aria-expanded', 'true');
  },

  close(sidebar, overlay) {
    sidebar.classList.remove('open');
    overlay?.classList.remove('active');
    document.body.style.overflow = '';
    const hamburger = document.getElementById('hamburger');
    if (hamburger) hamburger.setAttribute('aria-expanded', 'false');
  },

  setActiveLink() {
    const currentPath = window.location.pathname;
    document.querySelectorAll('.nav-link').forEach(link => {
      const href = link.getAttribute('href');
      if (!href) return;
      // Normalize relative href to compare against current path
      const normalizedHref = href.split('/').filter(p => p !== '..').join('/');
      const pageName = normalizedHref.split('/').pop();
      if (pageName && currentPath.endsWith('/' + pageName)) {
        link.classList.add('active');
      }
    });
  },
};

// ===== NOTIFICATION BELL =====
const NotifBell = {
  async init() {
    const bell = document.getElementById('notif-bell');
    if (!bell) return;

    await this.updateCount();

    bell.addEventListener('click', () => {
      window.location.href = 'notifications.html';
    });
  },

  async updateCount() {
    try {
      const data = await notificationsAPI.getAll();
      const unread = (data.notifications || []).filter(n => !n.is_read).length;
      const badge = document.getElementById('notif-badge');
      if (badge) {
        badge.textContent = unread > 99 ? '99+' : unread;
        badge.classList.toggle('hidden', unread === 0);
      }
    } catch {
      // Silently fail
    }
  },
};

// ===== HEADER USER INFO =====
const HeaderUser = {
  init() {
    const user = Storage.getUser();
    if (!user) return;

    const nameEl = document.getElementById('header-user-name');
    const avatarEl = document.getElementById('header-avatar');

    if (nameEl) nameEl.textContent = user.display_name || user.email || 'Pro Trader';

    if (avatarEl) {
      if (user.profile_picture_url) {
        avatarEl.src = user.profile_picture_url;
        avatarEl.alt = user.display_name || 'Profile';
      } else {
        const initials = (user.display_name || user.email || 'P')[0].toUpperCase();
        avatarEl.outerHTML = `<div class="avatar-placeholder" id="header-avatar">${initials}</div>`;
      }
    }

    // Logout button
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
      logoutBtn.addEventListener('click', () => Auth.logout());
    }
  },
};

// ===== APP INIT =====
const App = {
  async init() {
    // Initialize Toast
    Toast.init();

    // Initialize Realtime (non-blocking)
    Realtime.init(SUPABASE_URL, SUPABASE_ANON_KEY);

    // Initialize shared UI
    Sidebar.init();
    HeaderUser.init();

    // Notification bell (only on authenticated pages)
    if (Auth.isAuthenticated()) {
      await NotifBell.init();

      // Subscribe to realtime notifications
      const user = Storage.getUser();
      if (user?.id) {
        Realtime.subscribeToNotifications(user.id, (notif) => {
          Toast.show(notif.title || 'New notification', 'info');
          NotifBell.updateCount();
        });
      }
    }

    // Cleanup on page unload
    window.addEventListener('beforeunload', () => {
      Realtime.unsubscribeAll();
    });
  },
};

// ===== EXPORT FOR PAGES =====
export { App, Toast, Sidebar, NotifBell };
export default App;
