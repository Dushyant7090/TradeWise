/**
 * charts.js — Chart.js initialization for TradeWise Pro-Trader
 * Requires Chart.js loaded via CDN
 */

// ===== BRAND COLORS =====
const COLORS = {
  primary: '#10B981',
  primaryLight: 'rgba(16, 185, 129, 0.15)',
  danger: '#EF4444',
  dangerLight: 'rgba(239, 68, 68, 0.15)',
  warning: '#F59E0B',
  info: '#3B82F6',
  infoLight: 'rgba(59, 130, 246, 0.15)',
};

function getCssVar(name, fallback) {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

function getThemeTokens() {
  const isLight = document.documentElement.getAttribute('data-theme') === 'light';
  return {
    text: getCssVar('--text-muted', '#737373'),
    textPrimary: getCssVar('--text-primary', '#FFFFFF'),
    textSecondary: getCssVar('--text-secondary', '#A3A3A3'),
    gridLine: getCssVar('--border-subtle', isLight ? 'rgba(15, 23, 42, 0.12)' : 'rgba(255, 255, 255, 0.08)'),
    tooltipBg: isLight ? '#ffffff' : '#111827',
    tooltipBorder: getCssVar('--border-medium', isLight ? 'rgba(15, 23, 42, 0.18)' : 'rgba(255, 255, 255, 0.15)'),
    doughnutBorder: isLight ? '#f8fafc' : '#0a0a0a',
  };
}

function getSharedDefaults(theme) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        labels: {
          color: theme.text,
          font: { family: 'Inter', size: 12 },
          usePointStyle: true,
          pointStyleWidth: 10,
        },
      },
      tooltip: {
        backgroundColor: theme.tooltipBg,
        borderColor: theme.tooltipBorder,
        borderWidth: 1,
        titleColor: theme.textPrimary,
        bodyColor: theme.textSecondary,
        padding: 12,
        cornerRadius: 8,
      },
    },
  };
}

function getAxisDefaults(theme) {
  return {
    grid: { color: theme.gridLine },
    ticks: { color: theme.text, font: { family: 'Inter', size: 11 } },
  };
}

function replaceCanvasWithFallback(canvas, title, subtitle = '') {
  const parent = canvas?.parentElement;
  if (!parent) return null;
  parent.innerHTML = `
    <div class="chart-fallback" style="height:100%;min-height:180px;display:flex;align-items:center;justify-content:center;text-align:center;color:var(--text-muted);">
      <div>
        <div style="font-weight:700;color:var(--text-primary);margin-bottom:6px;">${title}</div>
        <div style="font-size:.85rem;">${subtitle}</div>
      </div>
    </div>`;
  return null;
}

function destroyExistingChart(canvas) {
  if (!window.Chart || !canvas) return;
  const existing = Chart.getChart(canvas);
  if (existing) existing.destroy();
}

// ===== ACCURACY TREND LINE CHART =====
export function createAccuracyChart(canvasId, data) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;
  if (!window.Chart) return replaceCanvasWithFallback(ctx, 'Chart library unavailable', 'Refresh the page to load the local chart bundle.');
  const theme = getThemeTokens();
  const sharedDefaults = getSharedDefaults(theme);
  const axisDefaults = getAxisDefaults(theme);

  const labels = data?.labels || [];
  const rawValues = data?.values || [];
  const currentValue = Number(data?.currentValue || 0);
  const values = rawValues.length
    ? rawValues.map((value) => Number(value || 0))
    : labels.map((_, index) => (index === labels.length - 1 ? currentValue : 0));
  if (!labels.length || !values.length) {
    return replaceCanvasWithFallback(ctx, 'No accuracy history yet', 'Close trades to build the trend.');
  }
  destroyExistingChart(ctx);

  return new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        {
          label: 'Accuracy %',
          data: values,
          borderColor: COLORS.primary,
          backgroundColor: COLORS.primaryLight,
          borderWidth: 2,
          pointBackgroundColor: COLORS.primary,
          pointRadius: 4,
          pointHoverRadius: 6,
          fill: true,
          tension: 0.4,
        },
      ],
    },
    options: {
      ...sharedDefaults,
      scales: {
        x: { ...axisDefaults },
        y: {
          ...axisDefaults,
          min: 0,
          max: 100,
          ticks: {
            ...axisDefaults.ticks,
            callback: (v) => `${v}%`,
          },
        },
      },
      plugins: {
        ...sharedDefaults.plugins,
        tooltip: {
          ...sharedDefaults.plugins.tooltip,
          callbacks: {
            label: (ctx) => ` ${ctx.parsed.y.toFixed(1)}%`,
          },
        },
      },
    },
  });
}

// ===== WIN/LOSS PIE CHART =====
export function createWinLossChart(canvasId, wins, losses) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;
  if (!window.Chart) return replaceCanvasWithFallback(ctx, 'Chart library unavailable', 'Refresh the page to load the local chart bundle.');
  destroyExistingChart(ctx);
  const theme = getThemeTokens();
  const sharedDefaults = getSharedDefaults(theme);

  return new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Wins', 'Losses'],
      datasets: [
        {
          data: [wins || 0, losses || 0],
          backgroundColor: [COLORS.primary, COLORS.danger],
          borderColor: [theme.doughnutBorder, theme.doughnutBorder],
          borderWidth: 3,
          hoverOffset: 6,
        },
      ],
    },
    options: {
      ...sharedDefaults,
      cutout: '68%',
      plugins: {
        ...sharedDefaults.plugins,
        legend: { ...sharedDefaults.plugins.legend, position: 'bottom' },
        tooltip: {
          ...sharedDefaults.plugins.tooltip,
          callbacks: {
            label: (ctx) => {
              const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
              const pct = total > 0 ? ((ctx.parsed / total) * 100).toFixed(1) : 0;
              return ` ${ctx.label}: ${ctx.parsed} (${pct}%)`;
            },
          },
        },
      },
    },
  });
}

// ===== MONTHLY EARNINGS BAR CHART =====
export function createEarningsChart(canvasId, data) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;
  if (!window.Chart) return replaceCanvasWithFallback(ctx, 'Chart library unavailable', 'Refresh the page to load the local chart bundle.');
  const theme = getThemeTokens();
  const sharedDefaults = getSharedDefaults(theme);
  const axisDefaults = getAxisDefaults(theme);

  const labels = data?.labels || [];
  const values = (data?.earnings || []).map((value) => Number(value || 0));
  if (!labels.length || !values.length) {
    return replaceCanvasWithFallback(ctx, 'No earnings yet', 'Subscription earnings will appear here.');
  }
  destroyExistingChart(ctx);

  return new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: 'Earnings (₹)',
          data: values,
          backgroundColor: COLORS.primaryLight,
          borderColor: COLORS.primary,
          borderWidth: 1,
          borderRadius: 6,
          borderSkipped: false,
        },
      ],
    },
    options: {
      ...sharedDefaults,
      scales: {
        x: { ...axisDefaults },
        y: {
          ...axisDefaults,
          ticks: {
            ...axisDefaults.ticks,
            callback: (v) => `₹${(v / 1000).toFixed(0)}k`,
          },
        },
      },
      plugins: {
        ...sharedDefaults.plugins,
        legend: { display: false },
        tooltip: {
          ...sharedDefaults.plugins.tooltip,
          callbacks: {
            label: (ctx) => ` ₹${ctx.parsed.y.toLocaleString('en-IN')}`,
          },
        },
        datalabels: false,
      },
    },
  });
}

// ===== RRR DISTRIBUTION HISTOGRAM =====
export function createRRRChart(canvasId, data) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return null;
  if (!window.Chart) return replaceCanvasWithFallback(ctx, 'Chart library unavailable', 'Refresh the page to load the local chart bundle.');
  destroyExistingChart(ctx);
  const theme = getThemeTokens();
  const sharedDefaults = getSharedDefaults(theme);
  const axisDefaults = getAxisDefaults(theme);

  const labels = data?.labels || ['<1', '1-1.5', '1.5-2', '2-3', '>3'];
  const values = data?.values || [];

  return new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: 'Trades',
          data: values,
          backgroundColor: [
            COLORS.dangerLight,
            'rgba(245, 158, 11, 0.2)',
            COLORS.infoLight,
            COLORS.primaryLight,
            COLORS.primaryLight,
          ],
          borderColor: [
            COLORS.danger,
            COLORS.warning,
            COLORS.info,
            COLORS.primary,
            COLORS.primary,
          ],
          borderWidth: 1,
          borderRadius: 6,
        },
      ],
    },
    options: {
      ...sharedDefaults,
      scales: {
        x: { ...axisDefaults },
        y: {
          ...axisDefaults,
          ticks: { ...axisDefaults.ticks, stepSize: 1 },
        },
      },
      plugins: {
        ...sharedDefaults.plugins,
        legend: { display: false },
      },
    },
  });
}

// ===== UPDATE CHART DATA =====
export function updateChart(chart, labels, datasets) {
  if (!chart) return;
  chart.data.labels = labels;
  datasets.forEach((d, i) => {
    if (chart.data.datasets[i]) {
      chart.data.datasets[i].data = d;
    }
  });
  chart.update('active');
}

// ===== DESTROY CHART =====
export function destroyChart(chart) {
  if (chart) chart.destroy();
}
