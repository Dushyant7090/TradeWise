/* =====================================================
   admin.js — TradeWise Admin Dashboard Logic
   ===================================================== */

'use strict';

/* ===== CONFIG ===== */
const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? 'http://localhost:5000/api'
  : '/api';

/* ===== AUTH ===== */
function getToken() { return localStorage.getItem('tw_admin_token'); }

function requireAuth() {
  if (!getToken()) { window.location.replace('../index.html'); }
}

function logout() {
  localStorage.removeItem('tw_admin_token');
  localStorage.removeItem('tw_admin_user');
  localStorage.removeItem('tw_admin_profile');
  window.location.replace('../index.html');
}

async function apiRequest(path, options = {}) {
  const token = getToken();
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  });
  if (res.status === 401) { logout(); return null; }
  return res;
}

/* ===== SECTION NAVIGATION ===== */
const sectionMap = {
  overview: 'Dashboard',
  analytics: 'Analytics',
  users: 'User Management',
  trades: 'Trade Monitoring',
  payouts: 'Pro-Trader Payouts',
  reports: 'Reports & Flags',
  comments: 'Comment Moderation',
  kyc: 'KYC Verification',
};

function switchSection(name) {
  // Update active section
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  const sec = document.getElementById(`section-${name}`);
  if (sec) sec.classList.add('active');

  // Update nav links
  document.querySelectorAll('.nav-link').forEach(l => {
    l.classList.toggle('active', l.dataset.section === name);
  });

  // Update page title
  const titleEl = document.getElementById('pageTitle');
  if (titleEl) titleEl.textContent = sectionMap[name] || name;

  // Lazy-load section data
  const loaders = {
    overview: loadStats,
    analytics: loadAnalytics,
    users: () => loadUsers(1),
    trades: () => loadTrades(1),
    payouts: () => loadPayouts(1),
    reports: () => loadReports(1),
    comments: () => loadComments(1),
    kyc: () => loadKYC(1),
  };
  if (loaders[name]) loaders[name]();

  // Close sidebar on mobile
  closeSidebar();
}

/* ===== SIDEBAR TOGGLE ===== */
function openSidebar() {
  document.getElementById('sidebar').classList.add('open');
  document.getElementById('sidebarOverlay').classList.add('active');
}
function closeSidebar() {
  document.getElementById('sidebar').classList.remove('open');
  document.getElementById('sidebarOverlay').classList.remove('active');
}

/* ===== TOAST ===== */
let toastTimer;
function showToast(message, type = 'success') {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.className = `toast toast-${type}`;
  toast.style.display = 'block';
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toast.style.display = 'none'; }, 3500);
}

/* ===== MODAL ===== */
function openModal(id) { document.getElementById(id).style.display = 'flex'; }
function closeModal(id) { document.getElementById(id).style.display = 'none'; }

/* ===== FORMATTING ===== */
function fmtCurrency(val) {
  if (val == null) return '—';
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(val);
}
function fmtDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}
function fmtDateShort(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short' });
}
function initials(name) {
  if (!name) return '?';
  return name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2);
}

function statusBadge(status) {
  const map = {
    active: ['badge-success', 'Active'],
    target_hit: ['badge-info', 'Target Hit'],
    sl_hit: ['badge-danger', 'SL Hit'],
    cancelled: ['badge-muted', 'Cancelled'],
    pending: ['badge-warning', 'Pending'],
    investigating: ['badge-info', 'Investigating'],
    resolved: ['badge-success', 'Resolved'],
    initiated: ['badge-warning', 'Initiated'],
    processing: ['badge-info', 'Processing'],
    success: ['badge-success', 'Paid'],
    failed: ['badge-danger', 'Failed'],
    verified: ['badge-success', 'Verified'],
    rejected: ['badge-danger', 'Rejected'],
  };
  const [cls, label] = map[status] || ['badge-muted', status || '—'];
  return `<span class="badge ${cls}">${label}</span>`;
}

/* ===== PAGINATION ===== */
function renderPagination(containerId, currentPage, totalPages, onPageChange) {
  const container = document.getElementById(containerId);
  if (!container) return;
  if (totalPages <= 1) { container.innerHTML = ''; return; }

  let html = `<span class="pagination-info">Page ${currentPage} of ${totalPages}</span>`;
  html += `<button class="pagination-btn" ${currentPage <= 1 ? 'disabled' : ''} onclick="(${onPageChange})(${currentPage - 1})">← Prev</button>`;

  // Window of pages
  const start = Math.max(1, currentPage - 2);
  const end = Math.min(totalPages, currentPage + 2);
  for (let p = start; p <= end; p++) {
    html += `<button class="pagination-btn ${p === currentPage ? 'active' : ''}" onclick="(${onPageChange})(${p})">${p}</button>`;
  }
  html += `<button class="pagination-btn" ${currentPage >= totalPages ? 'disabled' : ''} onclick="(${onPageChange})(${currentPage + 1})">Next →</button>`;
  container.innerHTML = html;
}

/* ===== STATS ===== */
async function loadStats() {
  try {
    const res = await apiRequest('/admin/stats');
    if (!res || !res.ok) return;
    const json = await res.json();

    document.getElementById('stat-active-users').textContent = json.active_users_30d?.toLocaleString() || '0';
    document.getElementById('stat-pro-traders').textContent = json.total_pro_traders?.toLocaleString() || '0';
    document.getElementById('stat-learners').textContent = json.total_learners?.toLocaleString() || '0';
    document.getElementById('stat-revenue').textContent = fmtCurrency(json.monthly_revenue);
    document.getElementById('stat-pending-payouts').textContent =
      `${fmtCurrency(json.pending_payouts_amount)} (${json.pending_payouts_count})`;
    document.getElementById('stat-flagged-trades').textContent = json.flagged_trades_month?.toLocaleString() || '0';
    document.getElementById('stat-pending-kyc').textContent = json.pending_kyc?.toLocaleString() || '0';
    document.getElementById('stat-open-reports').textContent = json.open_reports?.toLocaleString() || '0';

    // Remove loading state
    document.querySelectorAll('.stat-card.loading').forEach(c => c.classList.remove('loading'));

    // Update nav badges
    if (json.pending_payouts_count > 0) {
      const el = document.getElementById('payoutsCount');
      el.textContent = json.pending_payouts_count;
      el.classList.add('active');
    }
    if (json.open_reports > 0) {
      const el = document.getElementById('reportsCount');
      el.textContent = json.open_reports;
      el.classList.add('active');
    }
    if (json.pending_kyc > 0) {
      const el = document.getElementById('kycCount');
      el.textContent = json.pending_kyc;
      el.classList.add('active');
    }

    // Notifications
    buildNotifications(json);
  } catch (e) {
    console.error('loadStats error', e);
  }
}

function buildNotifications(stats) {
  const list = [];
  if (stats.pending_kyc > 0) {
    list.push({ type: 'warning', title: 'KYC Pending', desc: `${stats.pending_kyc} verification(s) awaiting review` });
  }
  if (stats.open_reports > 0) {
    list.push({ type: 'danger', title: 'Open Reports', desc: `${stats.open_reports} flagged item(s) need attention` });
  }
  if (stats.pending_payouts_count > 0) {
    list.push({ type: 'warning', title: 'Pending Payouts', desc: `${stats.pending_payouts_count} payout(s) awaiting processing` });
  }

  const notifList = document.getElementById('notifList');
  const notifDot = document.getElementById('notifDot');
  if (list.length === 0) {
    notifList.innerHTML = '<p class="notif-empty">No new notifications</p>';
    notifDot.style.display = 'none';
    return;
  }
  notifDot.style.display = 'block';
  notifList.innerHTML = list.map(n => `
    <div class="notif-item notif-${n.type}">
      <div class="notif-item-title">${n.title}</div>
      <div class="notif-item-desc">${n.desc}</div>
    </div>
  `).join('');
}

/* ===== CHARTS ===== */
let charts = {};

function destroyChart(id) {
  if (charts[id]) { charts[id].destroy(); delete charts[id]; }
}

const chartDefaults = {
  color: '#a3a3a3',
  font: { family: 'Inter, sans-serif', size: 11 },
};

Chart.defaults.color = chartDefaults.color;
Chart.defaults.font = chartDefaults.font;

async function loadAnalytics() {
  try {
    const [revRes, usersRes, flagsRes, payoutsRes] = await Promise.all([
      apiRequest('/admin/analytics/revenue'),
      apiRequest('/admin/analytics/users'),
      apiRequest('/admin/analytics/flags'),
      apiRequest('/admin/analytics/payouts'),
    ]);
    if (revRes?.ok) {
      const { data } = await revRes.json();
      buildChart('revenueChart', 'bar', data.map(d => d.month), [
        { label: 'Revenue (₹)', data: data.map(d => d.revenue), backgroundColor: 'rgba(16,185,129,0.6)', borderColor: '#10B981', borderWidth: 1 }
      ]);
    }
    if (usersRes?.ok) {
      const { data } = await usersRes.json();
      buildChart('usersChart', 'line', data.map(d => d.week), [
        { label: 'Registrations', data: data.map(d => d.users), borderColor: '#3B82F6', backgroundColor: 'rgba(59,130,246,0.15)', tension: 0.4, fill: true, pointRadius: 3 }
      ]);
    }
    if (flagsRes?.ok) {
      const { data } = await flagsRes.json();
      buildChart('flagsChart', 'bar', data.map(d => d.week), [
        { label: 'Reports', data: data.map(d => d.reports), backgroundColor: 'rgba(239,68,68,0.6)', borderColor: '#EF4444', borderWidth: 1 },
        { label: 'Learner Flags', data: data.map(d => d.learner_flags), backgroundColor: 'rgba(245,158,11,0.6)', borderColor: '#F59E0B', borderWidth: 1 },
      ], { stacked: true });
    }
    if (payoutsRes?.ok) {
      const { data } = await payoutsRes.json();
      buildChart('payoutsChart', 'line', data.map(d => d.month), [
        { label: 'Payouts (₹)', data: data.map(d => d.payouts), borderColor: '#8B5CF6', backgroundColor: 'rgba(139,92,246,0.15)', tension: 0.4, fill: true, pointRadius: 3 }
      ]);
    }
  } catch (e) {
    console.error('loadAnalytics error', e);
  }
}

function buildChart(canvasId, type, labels, datasets, extraScaleOptions = {}) {
  destroyChart(canvasId);
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  charts[canvasId] = new Chart(ctx, {
    type,
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { display: datasets.length > 1 },
        tooltip: { mode: 'index', intersect: false },
      },
      scales: {
        x: { grid: { color: 'rgba(255,255,255,0.05)' }, ticks: { maxRotation: 45 } },
        y: { grid: { color: 'rgba(255,255,255,0.05)' }, beginAtZero: true, stacked: extraScaleOptions.stacked || false },
      },
    },
  });
}

/* ===== USERS ===== */
let usersPage = 1;

async function loadUsers(page = 1) {
  usersPage = page;
  const search = document.getElementById('userSearch')?.value || '';
  const role = document.getElementById('userRoleFilter')?.value || '';
  const params = new URLSearchParams({ page, per_page: 20, search, role });

  const tbody = document.getElementById('usersTableBody');
  tbody.innerHTML = '<tr><td colspan="7" class="table-loading">Loading…</td></tr>';

  try {
    const res = await apiRequest(`/admin/users?${params}`);
    if (!res || !res.ok) { tbody.innerHTML = '<tr><td colspan="7" class="table-loading">Failed to load.</td></tr>'; return; }
    const json = await res.json();
    const users = json.users || [];

    if (users.length === 0) { tbody.innerHTML = '<tr><td colspan="7" class="table-loading">No users found.</td></tr>'; return; }

    tbody.innerHTML = users.map(u => `
      <tr>
        <td>
          <div class="user-cell">
            <div class="user-avatar">${initials(u.display_name || u.email)}</div>
            <div class="user-info">
              <div class="user-name">${esc(u.display_name || '—')}</div>
              <div class="user-email">${esc(u.email)}</div>
            </div>
          </div>
        </td>
        <td><span class="badge ${u.role === 'pro_trader' ? 'badge-info' : u.role === 'admin' ? 'badge-purple' : 'badge-muted'}">${u.role === 'public_trader' ? 'Learner' : u.role === 'pro_trader' ? 'Pro Trader' : u.role}</span></td>
        <td>${u.total_trades ?? '—'}</td>
        <td>${u.kyc_status ? statusBadge(u.kyc_status) : '<span class="badge badge-muted">N/A</span>'}</td>
        <td>${u.is_banned ? '<span class="badge badge-danger">Banned</span>' : !u.is_active ? '<span class="badge badge-warning">Suspended</span>' : '<span class="badge badge-success">Active</span>'}</td>
        <td>${fmtDate(u.created_at)}</td>
        <td>
          <div class="table-actions">
            ${!u.is_banned && u.is_active ? `<button class="btn btn-sm btn-warning" onclick="suspendUser('${u.id}','${esc(u.display_name || u.email)}')">Suspend</button>` : ''}
            ${!u.is_banned && !u.is_active ? `<button class="btn btn-sm btn-outline" onclick="reactivateUser('${u.id}','${esc(u.display_name || u.email)}')">Reactivate</button>` : ''}
            ${!u.is_banned ? `<button class="btn btn-sm btn-danger" onclick="confirmBan('${u.id}','${esc(u.display_name || u.email)}')">Ban</button>` : '<span class="badge badge-danger">Banned</span>'}
          </div>
        </td>
      </tr>
    `).join('');

    renderPagination('usersPagination', page, json.pages, (p) => loadUsers(p));
    // Update count badge
    const el = document.getElementById('usersCount');
    if (el && json.total) { el.textContent = json.total; el.classList.add('active'); }
  } catch (e) {
    tbody.innerHTML = '<tr><td colspan="7" class="table-loading">Error loading users.</td></tr>';
  }
}

async function suspendUser(userId, name) {
  if (!confirm(`Suspend user "${name}"? They will lose access until reactivated.`)) return;
  const res = await apiRequest(`/admin/users/${userId}/suspend`, { method: 'POST' });
  if (res?.ok) { showToast(`User "${name}" suspended.`); loadUsers(usersPage); }
  else { showToast('Failed to suspend user.', 'error'); }
}

async function reactivateUser(userId, name) {
  const res = await apiRequest(`/admin/users/${userId}/reactivate`, { method: 'POST' });
  if (res?.ok) { showToast(`User "${name}" reactivated.`); loadUsers(usersPage); }
  else { showToast('Failed to reactivate user.', 'error'); }
}

let pendingBanUserId = null;
function confirmBan(userId, name) {
  pendingBanUserId = userId;
  document.getElementById('banUserName').textContent = name;
  openModal('banModal');
}
async function executeBan() {
  if (!pendingBanUserId) return;
  const res = await apiRequest(`/admin/users/${pendingBanUserId}/ban`, { method: 'POST' });
  closeModal('banModal');
  if (res?.ok) { showToast('User permanently banned.'); loadUsers(usersPage); }
  else { showToast('Failed to ban user.', 'error'); }
  pendingBanUserId = null;
}

/* ===== TRADES ===== */
let tradesPage = 1;

async function loadTrades(page = 1) {
  tradesPage = page;
  const search = document.getElementById('tradeSearch')?.value || '';
  const status = document.getElementById('tradeStatusFilter')?.value || '';
  const flaggedOnly = document.getElementById('tradeFlaggedOnly')?.checked ? 'true' : 'false';
  const params = new URLSearchParams({ page, per_page: 20, search, status, flagged_only: flaggedOnly });

  const tbody = document.getElementById('tradesTableBody');
  tbody.innerHTML = '<tr><td colspan="9" class="table-loading">Loading…</td></tr>';

  try {
    const res = await apiRequest(`/admin/trades?${params}`);
    if (!res || !res.ok) { tbody.innerHTML = '<tr><td colspan="9" class="table-loading">Failed to load.</td></tr>'; return; }
    const json = await res.json();
    const trades = json.trades || [];

    if (trades.length === 0) { tbody.innerHTML = '<tr><td colspan="9" class="table-loading">No trades found.</td></tr>'; return; }

    tbody.innerHTML = trades.map(t => `
      <tr>
        <td><strong>${esc(t.symbol)}</strong></td>
        <td>${esc(t.trader_name || '—')}</td>
        <td><span class="badge ${t.direction === 'buy' ? 'badge-success' : 'badge-danger'}">${t.direction?.toUpperCase()}</span></td>
        <td>₹${Number(t.entry_price).toLocaleString()}</td>
        <td>${statusBadge(t.status)}</td>
        <td>${t.flag_count > 0 ? `<span class="badge badge-danger">${t.flag_count}</span>` : '0'}</td>
        <td>${t.unlock_count ?? 0}</td>
        <td>${fmtDateShort(t.created_at)}</td>
        <td>
          <div class="table-actions">
            ${t.flag_count > 0
              ? `<button class="btn btn-sm btn-outline" onclick="adminUnflagTrade('${t.id}')">Clear Flag</button>`
              : `<button class="btn btn-sm btn-warning" onclick="adminFlagTrade('${t.id}')">Flag</button>`}
          </div>
        </td>
      </tr>
    `).join('');

    renderPagination('tradesPagination', page, json.pages, (p) => loadTrades(p));
  } catch (e) {
    tbody.innerHTML = '<tr><td colspan="9" class="table-loading">Error loading trades.</td></tr>';
  }
}

async function adminFlagTrade(tradeId) {
  const res = await apiRequest(`/admin/trades/${tradeId}/flag`, { method: 'POST' });
  if (res?.ok) { showToast('Trade flagged.'); loadTrades(tradesPage); }
  else { showToast('Failed.', 'error'); }
}
async function adminUnflagTrade(tradeId) {
  const res = await apiRequest(`/admin/trades/${tradeId}/unflag`, { method: 'POST' });
  if (res?.ok) { showToast('Trade flags cleared.'); loadTrades(tradesPage); }
  else { showToast('Failed.', 'error'); }
}

/* ===== PAYOUTS ===== */
let payoutsPage = 1;

async function loadPayouts(page = 1) {
  payoutsPage = page;
  const search = document.getElementById('payoutSearch')?.value || '';
  const status = document.getElementById('payoutStatusFilter')?.value || '';
  const params = new URLSearchParams({ page, per_page: 20, search, status });

  const tbody = document.getElementById('payoutsTableBody');
  tbody.innerHTML = '<tr><td colspan="8" class="table-loading">Loading…</td></tr>';

  try {
    const res = await apiRequest(`/admin/payouts?${params}`);
    if (!res || !res.ok) { tbody.innerHTML = '<tr><td colspan="8" class="table-loading">Failed to load.</td></tr>'; return; }
    const json = await res.json();
    const payouts = json.payouts || [];

    if (payouts.length === 0) { tbody.innerHTML = '<tr><td colspan="8" class="table-loading">No payouts found.</td></tr>'; return; }

    tbody.innerHTML = payouts.map(p => `
      <tr>
        <td>${esc(p.trader_name || '—')}</td>
        <td><span class="user-email">${esc(p.trader_email || '—')}</span></td>
        <td><strong>${fmtCurrency(p.amount)}</strong></td>
        <td>${p.bank_account_last_4 ? `****${p.bank_account_last_4}` : '—'}</td>
        <td>${statusBadge(p.status)}</td>
        <td>${fmtDate(p.initiated_at)}</td>
        <td>${fmtDate(p.completed_at)}</td>
        <td>
          <div class="table-actions">
            ${p.status !== 'success' ? `<button class="btn btn-sm btn-primary" onclick="markPayoutPaid('${p.id}')">Mark Paid</button>` : ''}
            ${p.status === 'success' ? `<button class="btn btn-sm btn-outline" onclick="markPayoutUnpaid('${p.id}')">Mark Unpaid</button>` : ''}
          </div>
        </td>
      </tr>
    `).join('');

    renderPagination('payoutsPagination', page, json.pages, (p) => loadPayouts(p));
  } catch (e) {
    tbody.innerHTML = '<tr><td colspan="8" class="table-loading">Error loading payouts.</td></tr>';
  }
}

async function markPayoutPaid(payoutId) {
  const res = await apiRequest(`/admin/payouts/${payoutId}/mark-paid`, { method: 'POST' });
  if (res?.ok) { showToast('Payout marked as paid.'); loadPayouts(payoutsPage); }
  else { showToast('Failed.', 'error'); }
}
async function markPayoutUnpaid(payoutId) {
  const res = await apiRequest(`/admin/payouts/${payoutId}/mark-unpaid`, { method: 'POST' });
  if (res?.ok) { showToast('Payout marked as unpaid.'); loadPayouts(payoutsPage); }
  else { showToast('Failed.', 'error'); }
}

/* ===== REPORTS ===== */
let reportsPage = 1;

async function loadReports(page = 1) {
  reportsPage = page;
  const status = document.getElementById('reportStatusFilter')?.value || '';
  const params = new URLSearchParams({ page, per_page: 20, status });

  const tbody = document.getElementById('reportsTableBody');
  tbody.innerHTML = '<tr><td colspan="6" class="table-loading">Loading…</td></tr>';

  try {
    const res = await apiRequest(`/admin/reports?${params}`);
    if (!res || !res.ok) { tbody.innerHTML = '<tr><td colspan="6" class="table-loading">Failed to load.</td></tr>'; return; }
    const json = await res.json();
    const reports = json.reports || [];

    if (reports.length === 0) { tbody.innerHTML = '<tr><td colspan="6" class="table-loading">No reports found.</td></tr>'; return; }

    tbody.innerHTML = reports.map(r => `
      <tr>
        <td>${esc(r.reporter_name || r.reporter_id?.slice(0, 8) + '…' || '—')}</td>
        <td>${esc(r.trade_symbol || r.trade_id?.slice(0, 8) + '…' || '—')}</td>
        <td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${esc(r.reason)}">${esc(r.reason)}</td>
        <td>${statusBadge(r.status)}</td>
        <td>${fmtDate(r.created_at)}</td>
        <td>
          <div class="table-actions">
            ${r.status !== 'resolved' ? `
              <button class="btn btn-sm btn-primary" onclick="openResolveModal('${r.id}', 'resolve')">Resolve</button>
              <button class="btn btn-sm btn-outline" onclick="openResolveModal('${r.id}', 'dismiss')">Dismiss</button>
            ` : '<span class="badge badge-muted">Closed</span>'}
          </div>
        </td>
      </tr>
    `).join('');

    renderPagination('reportsPagination', page, json.pages, (p) => loadReports(p));
  } catch (e) {
    tbody.innerHTML = '<tr><td colspan="6" class="table-loading">Error loading reports.</td></tr>';
  }
}

let pendingReportId = null;
let pendingReportAction = null;
function openResolveModal(reportId, action) {
  pendingReportId = reportId;
  pendingReportAction = action;
  document.getElementById('resolveModalTitle').textContent = action === 'resolve' ? 'Resolve Report' : 'Dismiss Report';
  document.getElementById('resolveVerdict').value = '';
  openModal('resolveModal');
}
async function executeResolve() {
  if (!pendingReportId) return;
  const verdict = document.getElementById('resolveVerdict').value.trim();
  const endpoint = pendingReportAction === 'dismiss' ? 'dismiss' : 'resolve';
  const res = await apiRequest(`/admin/reports/${pendingReportId}/${endpoint}`, {
    method: 'POST',
    body: JSON.stringify({ verdict, note: verdict }),
  });
  closeModal('resolveModal');
  if (res?.ok) { showToast(`Report ${endpoint === 'dismiss' ? 'dismissed' : 'resolved'}.`); loadReports(reportsPage); loadStats(); }
  else { showToast('Failed.', 'error'); }
  pendingReportId = null;
}

/* ===== COMMENTS ===== */
let commentsPage = 1;

async function loadComments(page = 1) {
  commentsPage = page;
  const tradeId = document.getElementById('commentSearch')?.value || '';
  const params = new URLSearchParams({ page, per_page: 20, ...(tradeId ? { trade_id: tradeId } : {}) });

  const tbody = document.getElementById('commentsTableBody');
  tbody.innerHTML = '<tr><td colspan="5" class="table-loading">Loading…</td></tr>';

  try {
    const res = await apiRequest(`/admin/comments?${params}`);
    if (!res || !res.ok) { tbody.innerHTML = '<tr><td colspan="5" class="table-loading">Failed to load.</td></tr>'; return; }
    const json = await res.json();
    const comments = json.comments || [];

    if (comments.length === 0) { tbody.innerHTML = '<tr><td colspan="5" class="table-loading">No comments found.</td></tr>'; return; }

    tbody.innerHTML = comments.map(c => `
      <tr>
        <td>${esc(c.author_name || '—')}</td>
        <td><span class="badge badge-muted">${esc(c.trade_symbol || c.trade_id?.slice(0, 8) + '…' || '—')}</span></td>
        <td style="max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${esc(c.content)}">${esc(c.content)}</td>
        <td>${fmtDate(c.created_at)}</td>
        <td>
          <div class="table-actions">
            <button class="btn btn-sm btn-outline" onclick="openReplyModal('${c.id}', '${esc(c.content?.slice(0,60))}')">Reply</button>
            <button class="btn btn-sm btn-danger" onclick="deleteComment('${c.id}')">Delete</button>
          </div>
        </td>
      </tr>
    `).join('');

    renderPagination('commentsPagination', page, json.pages, (p) => loadComments(p));
  } catch (e) {
    tbody.innerHTML = '<tr><td colspan="5" class="table-loading">Error loading comments.</td></tr>';
  }
}

let pendingReplyCommentId = null;
function openReplyModal(commentId, preview) {
  pendingReplyCommentId = commentId;
  document.getElementById('replyPreview').textContent = preview;
  document.getElementById('replyContent').value = '';
  openModal('replyModal');
}
async function executeReply() {
  if (!pendingReplyCommentId) return;
  const content = document.getElementById('replyContent').value.trim();
  if (!content) { showToast('Reply cannot be empty.', 'error'); return; }
  const res = await apiRequest(`/admin/comments/${pendingReplyCommentId}/reply`, {
    method: 'POST',
    body: JSON.stringify({ content }),
  });
  closeModal('replyModal');
  if (res?.ok) { showToast('Reply posted.'); loadComments(commentsPage); }
  else { showToast('Failed to post reply.', 'error'); }
  pendingReplyCommentId = null;
}

async function deleteComment(commentId) {
  if (!confirm('Delete this comment? This cannot be undone.')) return;
  const res = await apiRequest(`/admin/comments/${commentId}`, { method: 'DELETE' });
  if (res?.ok) { showToast('Comment deleted.'); loadComments(commentsPage); }
  else { showToast('Failed to delete comment.', 'error'); }
}

/* ===== KYC ===== */
let kycPage = 1;

async function loadKYC(page = 1) {
  kycPage = page;
  const status = document.getElementById('kycStatusFilter')?.value || 'pending';
  const params = new URLSearchParams({ page, per_page: 20, status });

  const tbody = document.getElementById('kycTableBody');
  tbody.innerHTML = '<tr><td colspan="6" class="table-loading">Loading…</td></tr>';

  try {
    const res = await apiRequest(`/admin/kyc?${params}`);
    if (!res || !res.ok) { tbody.innerHTML = '<tr><td colspan="6" class="table-loading">Failed to load.</td></tr>'; return; }
    const json = await res.json();
    const requests = json.kyc_requests || [];

    if (requests.length === 0) { tbody.innerHTML = '<tr><td colspan="6" class="table-loading">No KYC requests found.</td></tr>'; return; }

    tbody.innerHTML = requests.map(k => `
      <tr>
        <td>
          <div class="user-cell">
            <div class="user-avatar">${initials(k.display_name || k.email)}</div>
            <div class="user-info">
              <div class="user-name">${esc(k.display_name || '—')}</div>
            </div>
          </div>
        </td>
        <td><span class="user-email">${esc(k.email || '—')}</span></td>
        <td><span class="badge badge-info">${k.document_count || 0} doc(s)</span></td>
        <td>${statusBadge(k.kyc_status)}</td>
        <td>${fmtDate(k.created_at)}</td>
        <td>
          <div class="table-actions">
            ${k.kyc_status === 'pending' ? `
              <button class="btn btn-sm btn-primary" onclick="approveKYC('${k.user_id}','${esc(k.display_name || '')}')">Approve</button>
              <button class="btn btn-sm btn-danger" onclick="rejectKYC('${k.user_id}','${esc(k.display_name || '')}')">Reject</button>
            ` : `<span class="badge badge-muted">Processed</span>`}
          </div>
        </td>
      </tr>
    `).join('');

    renderPagination('kycPagination', page, json.pages, (p) => loadKYC(p));
  } catch (e) {
    tbody.innerHTML = '<tr><td colspan="6" class="table-loading">Error loading KYC requests.</td></tr>';
  }
}

async function approveKYC(userId, name) {
  if (!confirm(`Approve KYC for "${name}"?`)) return;
  const res = await apiRequest(`/admin/kyc/${userId}/approve`, { method: 'POST' });
  if (res?.ok) { showToast(`KYC approved for "${name}".`); loadKYC(kycPage); loadStats(); }
  else { showToast('Failed to approve KYC.', 'error'); }
}
async function rejectKYC(userId, name) {
  if (!confirm(`Reject KYC for "${name}"? They will need to resubmit.`)) return;
  const res = await apiRequest(`/admin/kyc/${userId}/reject`, { method: 'POST' });
  if (res?.ok) { showToast(`KYC rejected for "${name}".`); loadKYC(kycPage); loadStats(); }
  else { showToast('Failed to reject KYC.', 'error'); }
}

/* ===== CSV EXPORT ===== */
async function adminExport(type) {
  const endpoints = {
    users: '/admin/export/users',
    trades: '/admin/export/trades',
    payouts: '/admin/export/payouts',
    reports: '/admin/export/reports',
  };
  const url = endpoints[type];
  if (!url) return;

  try {
    const token = getToken();
    const res = await fetch(`${API_BASE}${url}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) { showToast('Export failed.', 'error'); return; }
    const blob = await res.blob();
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `tradewise_${type}_${new Date().toISOString().slice(0,10)}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
    showToast('CSV exported successfully.');
  } catch (e) {
    showToast('Export failed.', 'error');
  }
}

// Alias used by analytics section buttons
function exportCSV(type) {
  if (type === 'revenue') adminExport('payouts');
  else if (type === 'payouts-chart') adminExport('payouts');
}

/* ===== ESCAPE ===== */
function esc(str) {
  if (str == null) return '';
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

/* ===== INIT ===== */
document.addEventListener('DOMContentLoaded', () => {
  requireAuth();

  // Load admin profile display
  const profile = JSON.parse(localStorage.getItem('tw_admin_profile') || '{}');
  const user = JSON.parse(localStorage.getItem('tw_admin_user') || '{}');
  const displayName = profile.display_name || user.email?.split('@')[0] || 'Admin';
  const nameEl = document.getElementById('adminName');
  const avatarEl = document.getElementById('adminAvatar');
  if (nameEl) nameEl.textContent = displayName;
  if (avatarEl) avatarEl.textContent = initials(displayName);

  // Overview date
  const overviewDateEl = document.getElementById('overviewDate');
  if (overviewDateEl) overviewDateEl.textContent = new Date().toLocaleDateString('en-IN', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' });

  // Sidebar navigation
  document.querySelectorAll('.nav-link[data-section]').forEach(link => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      switchSection(link.dataset.section);
    });
  });

  // Sidebar toggle (mobile)
  document.getElementById('sidebarToggleBtn')?.addEventListener('click', openSidebar);
  document.getElementById('sidebarCloseBtn')?.addEventListener('click', closeSidebar);
  document.getElementById('sidebarOverlay')?.addEventListener('click', closeSidebar);

  // Logout
  document.getElementById('logoutBtn')?.addEventListener('click', logout);

  // Refresh
  document.getElementById('refreshBtn')?.addEventListener('click', () => {
    const activeSection = document.querySelector('.section.active')?.id?.replace('section-', '') || 'overview';
    switchSection(activeSection);
    showToast('Data refreshed.');
  });

  // Notification panel toggle
  document.getElementById('notifBtn')?.addEventListener('click', () => {
    const panel = document.getElementById('notifPanel');
    panel.style.display = panel.style.display === 'none' ? 'flex' : 'none';
    panel.style.flexDirection = 'column';
  });
  document.getElementById('notifClose')?.addEventListener('click', () => {
    document.getElementById('notifPanel').style.display = 'none';
  });

  // Filter live search debounce
  let debounceTimer;
  function debounce(fn) {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(fn, 350);
  }
  document.getElementById('userSearch')?.addEventListener('input', () => debounce(() => loadUsers(1)));
  document.getElementById('userRoleFilter')?.addEventListener('change', () => loadUsers(1));
  document.getElementById('tradeSearch')?.addEventListener('input', () => debounce(() => loadTrades(1)));
  document.getElementById('tradeStatusFilter')?.addEventListener('change', () => loadTrades(1));
  document.getElementById('tradeFlaggedOnly')?.addEventListener('change', () => loadTrades(1));
  document.getElementById('payoutSearch')?.addEventListener('input', () => debounce(() => loadPayouts(1)));
  document.getElementById('payoutStatusFilter')?.addEventListener('change', () => loadPayouts(1));
  document.getElementById('reportStatusFilter')?.addEventListener('change', () => loadReports(1));
  document.getElementById('commentSearch')?.addEventListener('input', () => debounce(() => loadComments(1)));
  document.getElementById('kycStatusFilter')?.addEventListener('change', () => loadKYC(1));

  // Modal confirm buttons
  document.getElementById('banConfirmBtn')?.addEventListener('click', executeBan);
  document.getElementById('resolveConfirmBtn')?.addEventListener('click', executeResolve);
  document.getElementById('replyConfirmBtn')?.addEventListener('click', executeReply);

  // Close modals on overlay click
  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) overlay.style.display = 'none';
    });
  });

  // Load initial overview
  loadStats();
});
