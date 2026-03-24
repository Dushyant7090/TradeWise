/**
 * charts.js — Chart.js initialization for TradeWise Learner
 * Requires Chart.js loaded via CDN
 */

// ===== BRAND COLORS =====
const COLORS = {
  primary: '#10B981',
  primaryLight: 'rgba(16, 185, 129, 0.15)',
  danger: '#EF4444',
  dangerLight: 'rgba(239, 68, 68, 0.15)',
  warning: '#F59E0B',
  warningLight: 'rgba(245, 158, 11, 0.15)',
  info: '#3B82F6',
  infoLight: 'rgba(59, 130, 246, 0.15)',
  gridLine: 'rgba(255, 255, 255, 0.05)',
  text: '#737373',
};

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

// ===== CREDITS OVER TIME (LINE) =====
export function createCreditsChart(canvasId, data) {
  const ctx = document.getElementById(canvasId);
  if (!ctx || !window.Chart) return null;
  return new Chart(ctx, {
    type: 'line',
    data: {
      labels: data?.labels || [],
      datasets: [{
        label: 'Credits',
        data: data?.values || [],
        borderColor: COLORS.primary,
        backgroundColor: COLORS.primaryLight,
        borderWidth: 2,
        pointBackgroundColor: COLORS.primary,
        pointRadius: 4,
        pointHoverRadius: 6,
        fill: true,
        tension: 0.4,
      }],
    },
    options: {
      ...sharedDefaults,
      scales: {
        x: { ...axisDefaults },
        y: { ...axisDefaults, min: 0, max: 7, ticks: { ...axisDefaults.ticks, stepSize: 1 } },
      },
      plugins: { ...sharedDefaults.plugins, legend: { display: false } },
    },
  });
}

// ===== MARKET DISTRIBUTION (DOUGHNUT) =====
export function createMarketDistributionChart(canvasId, data) {
  const ctx = document.getElementById(canvasId);
  if (!ctx || !window.Chart) return null;
  const labels = data?.labels || [];
  const values = data?.values || [];
  const palette = [COLORS.primary, COLORS.info, COLORS.warning, COLORS.danger, '#8B5CF6', '#EC4899'];
  return new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: palette.slice(0, labels.length),
        borderColor: '#0a0a0a',
        borderWidth: 3,
        hoverOffset: 6,
      }],
    },
    options: {
      ...sharedDefaults,
      cutout: '65%',
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

// ===== WIN/LOSS TRACKING (BAR) =====
export function createWinLossChart(canvasId, data) {
  const ctx = document.getElementById(canvasId);
  if (!ctx || !window.Chart) return null;
  return new Chart(ctx, {
    type: 'bar',
    data: {
      labels: data?.labels || [],
      datasets: [
        {
          label: 'Target Hit',
          data: data?.wins || [],
          backgroundColor: COLORS.primaryLight,
          borderColor: COLORS.primary,
          borderWidth: 1,
          borderRadius: 4,
        },
        {
          label: 'SL Hit',
          data: data?.losses || [],
          backgroundColor: COLORS.dangerLight,
          borderColor: COLORS.danger,
          borderWidth: 1,
          borderRadius: 4,
        },
      ],
    },
    options: {
      ...sharedDefaults,
      scales: {
        x: { ...axisDefaults, stacked: false },
        y: { ...axisDefaults, beginAtZero: true, ticks: { ...axisDefaults.ticks, stepSize: 1 } },
      },
    },
  });
}

// ===== LEARNING PROGRESS — TRADES UNLOCKED OVER TIME (AREA) =====
export function createLearningProgressChart(canvasId, data) {
  const ctx = document.getElementById(canvasId);
  if (!ctx || !window.Chart) return null;
  return new Chart(ctx, {
    type: 'line',
    data: {
      labels: data?.labels || [],
      datasets: [{
        label: 'Trades Unlocked',
        data: data?.values || [],
        borderColor: COLORS.info,
        backgroundColor: COLORS.infoLight,
        borderWidth: 2,
        pointBackgroundColor: COLORS.info,
        pointRadius: 4,
        fill: true,
        tension: 0.4,
      }],
    },
    options: {
      ...sharedDefaults,
      scales: {
        x: { ...axisDefaults },
        y: { ...axisDefaults, beginAtZero: true, ticks: { ...axisDefaults.ticks, stepSize: 1 } },
      },
      plugins: { ...sharedDefaults.plugins, legend: { display: false } },
    },
  });
}

// ===== MONTHLY UNLOCKS (BAR) =====
export function createMonthlyUnlocksChart(canvasId, data) {
  const ctx = document.getElementById(canvasId);
  if (!ctx || !window.Chart) return null;
  return new Chart(ctx, {
    type: 'bar',
    data: {
      labels: data?.labels || [],
      datasets: [{
        label: 'Unlocks',
        data: data?.values || [],
        backgroundColor: COLORS.warningLight,
        borderColor: COLORS.warning,
        borderWidth: 1,
        borderRadius: 6,
        borderSkipped: false,
      }],
    },
    options: {
      ...sharedDefaults,
      scales: {
        x: { ...axisDefaults },
        y: { ...axisDefaults, beginAtZero: true, ticks: { ...axisDefaults.ticks, stepSize: 1 } },
      },
      plugins: { ...sharedDefaults.plugins, legend: { display: false } },
    },
  });
}

// ===== UTILITIES =====
export function updateChart(chart, labels, datasets) {
  if (!chart) return;
  chart.data.labels = labels;
  datasets.forEach((d, i) => {
    if (chart.data.datasets[i]) chart.data.datasets[i].data = d;
  });
  chart.update('active');
}

export function destroyChart(chart) {
  if (chart) chart.destroy();
}
