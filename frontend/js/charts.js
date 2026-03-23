/**
 * charts.js — Chart.js initialization for TradeWise Pro-Trader
 * Requires Chart.js loaded via CDN
 */

import { getCSSVar } from './utils.js';

// ===== BRAND COLORS =====
const COLORS = {
  primary: '#10B981',
  primaryLight: 'rgba(16, 185, 129, 0.15)',
  danger: '#EF4444',
  dangerLight: 'rgba(239, 68, 68, 0.15)',
  warning: '#F59E0B',
  info: '#3B82F6',
  infoLight: 'rgba(59, 130, 246, 0.15)',
  gridLine: 'rgba(255, 255, 255, 0.05)',
  text: '#737373',
};

// Shared chart defaults
const sharedDefaults = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      labels: {
        color: COLORS.text,
        font: { family: 'Inter', size: 12 },
        usePointStyle: true,
        pointStyleWidth: 10,
      },
    },
    tooltip: {
      backgroundColor: '#1a1a1a',
      borderColor: 'rgba(255,255,255,0.1)',
      borderWidth: 1,
      titleColor: '#fff',
      bodyColor: '#A3A3A3',
      padding: 12,
      cornerRadius: 8,
    },
  },
};

const axisDefaults = {
  grid: { color: COLORS.gridLine },
  ticks: { color: COLORS.text, font: { family: 'Inter', size: 11 } },
};

// ===== ACCURACY TREND LINE CHART =====
export function createAccuracyChart(canvasId, data) {
  const ctx = document.getElementById(canvasId);
  if (!ctx || !window.Chart) return null;

  const labels = data?.labels || [];
  const values = data?.values || [];

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
  if (!ctx || !window.Chart) return null;

  return new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Wins', 'Losses'],
      datasets: [
        {
          data: [wins || 0, losses || 0],
          backgroundColor: [COLORS.primary, COLORS.danger],
          borderColor: ['#0a0a0a', '#0a0a0a'],
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
  if (!ctx || !window.Chart) return null;

  const labels = data?.labels || [];
  const values = data?.earnings || [];

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
  if (!ctx || !window.Chart) return null;

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
