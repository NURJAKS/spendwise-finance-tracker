let doughnutChart = null;
let comparisonChart = null;
let forecastChart = null;

function readCssVar(name, fallback) {
  const val = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return val || fallback;
}

function chartTheme() {
  return {
    cardBg: readCssVar('--card', '#131826'),
    text: readCssVar('--text', '#EEF1F8'),
    muted: readCssVar('--muted', '#8B95AC'),
    grid: readCssVar('--border', 'rgba(255,255,255,0.08)'),
    accent: readCssVar('--accent', '#6C7CFF'),
    prevColor: '#F59E0B',
    green: readCssVar('--green', '#34C38F'),
    red: readCssVar('--red', '#F4616F'),
  };
}

function renderDoughnutChart(stats, fmtMoney, activeCategoryId, onCategoryClick) {
  const wrap = document.getElementById('chartWrap');
  const empty = document.getElementById('chartEmpty');
  const legend = document.getElementById('legend');
  const has = stats.length > 0;
  const theme = chartTheme();

  wrap.hidden = !has;
  empty.hidden = has;
  legend.replaceChildren();

  if (!has) {
    if (doughnutChart) {
      doughnutChart.destroy();
      doughnutChart = null;
    }
    return;
  }

  const data = {
    labels: stats.map((s) => s.name),
    datasets: [
      {
        data: stats.map((s) => s.total),
        backgroundColor: stats.map((s) =>
          activeCategoryId && s.category_id !== activeCategoryId ? s.color + '44' : s.color
        ),
        borderColor: theme.cardBg,
        borderWidth: 3,
        hoverOffset: 7,
      },
    ],
  };

  if (doughnutChart) {
    doughnutChart.data = data;
    doughnutChart.update();
  } else {
    doughnutChart = new Chart(document.getElementById('chart'), {
      type: 'doughnut',
      data,
      options: {
        cutout: '68%',
        animation: { duration: 450 },
        onClick: (_, elements) => {
          if (elements.length > 0 && onCategoryClick) {
            const idx = elements[0].index;
            onCategoryClick(stats[idx].category_id);
          }
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (c) => ` ${c.label}: ${fmtMoney(c.parsed)}`,
            },
          },
        },
      },
    });
  }

  doughnutChart.$stats = stats;
  doughnutChart.options.onClick = (_, elements) => {
    if (elements.length > 0 && onCategoryClick) {
      const idx = elements[0].index;
      onCategoryClick(doughnutChart.$stats[idx].category_id);
    }
  };

  stats.forEach((s) => {
    const li = document.createElement('li');
    li.className = 'legend-item' + (activeCategoryId === s.category_id ? ' active' : '');
    li.setAttribute('role', 'button');
    li.setAttribute('tabindex', '0');
    const toggle = () => onCategoryClick && onCategoryClick(s.category_id);
    li.addEventListener('click', toggle);
    li.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        toggle();
      }
    });

    const dot = document.createElement('span');
    dot.className = 'dot';
    dot.style.background = s.color;

    const nameEl = document.createElement('span');
    nameEl.className = 'name';
    nameEl.textContent = s.name;

    const sumEl = document.createElement('span');
    sumEl.className = 'sum';
    sumEl.textContent = fmtMoney(s.total);

    const pctEl = document.createElement('span');
    pctEl.className = 'pct';
    pctEl.textContent = s.percent + '%';

    li.append(dot, nameEl, sumEl, pctEl);
    legend.append(li);
  });
}

function renderComparisonChart(comp, compViewMode, fmtMoney) {
  const wrap = document.getElementById('comparisonWrap');
  const empty = document.getElementById('comparisonEmpty');
  const theme = chartTheme();

  const isEmpty =
    !comp ||
    comp.labels.length === 0 ||
    (comp.current_total === 0 && comp.previous_total === 0);

  wrap.hidden = isEmpty;
  empty.hidden = !isEmpty;

  if (isEmpty) {
    if (comparisonChart) {
      comparisonChart.destroy();
      comparisonChart = null;
    }
    return;
  }

  const useCumulative = comp.mode === 'timeline' && compViewMode === 'cumulative';
  const curSeries = useCumulative ? comp.current_cumulative : comp.current_daily;
  const prevSeries = useCumulative ? comp.previous_cumulative : comp.previous_daily;

  const isCategoryDayMode = comp.mode === 'category';
  const chartType = isCategoryDayMode || compViewMode === 'daily' ? 'bar' : 'line';

  const curColor = comp.type === 'income' ? theme.green : theme.accent;
  const prevColor = theme.prevColor;

  const datasets =
    chartType === 'line'
      ? [
          {
            label: `Текущий (${comp.current_label})`,
            data: curSeries,
            borderColor: curColor,
            backgroundColor: curColor + '26',
            borderWidth: 3,
            tension: 0.3,
            fill: true,
            pointRadius: 2.5,
            pointHoverRadius: 5,
            spanGaps: false,
            order: 1,
          },
          {
            label: `Прошлый (${comp.previous_label})`,
            data: prevSeries,
            borderColor: prevColor,
            backgroundColor: 'transparent',
            borderWidth: 2.2,
            borderDash: [6, 5],
            tension: 0.3,
            fill: false,
            pointRadius: 1.8,
            pointHoverRadius: 4.5,
            spanGaps: false,
            order: 2,
          },
        ]
      : [
          {
            label: `Текущий (${comp.current_label})`,
            data: curSeries,
            backgroundColor: curColor + 'CC',
            borderColor: curColor,
            borderWidth: 1.5,
            borderRadius: 6,
            grouped: false,
            barPercentage: 0.52,
            order: 1,
          },
          {
            label: `Прошлый (${comp.previous_label})`,
            data: prevSeries,
            backgroundColor: prevColor + '45',
            borderColor: prevColor,
            borderWidth: 1.5,
            borderRadius: 6,
            grouped: false,
            barPercentage: 0.8,
            order: 2,
          },
        ];

  if (comparisonChart) {
    comparisonChart.destroy();
  }

  comparisonChart = new Chart(document.getElementById('comparisonChart'), {
    type: chartType,
    data: {
      labels: comp.labels,
      datasets,
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      animation: { duration: 400 },
      plugins: {
        legend: {
          display: true,
          position: 'top',
          align: 'end',
          labels: {
            color: theme.muted,
            boxWidth: 12,
            boxHeight: 12,
            usePointStyle: chartType === 'line',
            font: { family: 'Manrope, sans-serif', size: 12, weight: '600' },
          },
        },
        tooltip: {
          callbacks: {
            title: (items) => {
              if (!items.length) return '';
              const lbl = items[0].label;
              if (comp.mode === 'timeline' && comp.period === 'month') return `${lbl}-е число`;
              return lbl;
            },
            label: (c) => {
              if (c.parsed.y === null || c.parsed.y === undefined) return null;
              return ` ${c.dataset.label}: ${fmtMoney(c.parsed.y)}`;
            },
          },
        },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: {
            color: theme.muted,
            maxRotation: 0,
            autoSkip: true,
            maxTicksLimit: 11,
            font: { size: 11 },
          },
        },
        y: {
          beginAtZero: true,
          grid: { color: theme.grid },
          ticks: {
            color: theme.muted,
            font: { size: 11 },
            callback: (val) => (val >= 1000 ? Math.round(val / 1000) + 'k' : val),
          },
        },
      },
    },
  });
}

function renderForecastChart(forecast, fmtMoney) {
  const wrap = document.getElementById('forecastChartWrap');
  const empty = document.getElementById('forecastEmpty');
  const theme = chartTheme();

  const points = forecast && forecast.history ? forecast.history : [];
  const hasAny = points.some((p) => p.actual_expense > 0 || (p.projected_expense || 0) > 0);

  wrap.hidden = !hasAny;
  empty.hidden = hasAny;

  if (!hasAny) {
    if (forecastChart) {
      forecastChart.destroy();
      forecastChart = null;
    }
    return;
  }

  const labels = points.map((p) => p.label);
  const actualData = points.map((p) => (p.is_forecast ? null : p.actual_expense));
  const forecastData = points.map((p) => {
    if (p.is_forecast) return p.projected_expense;
    if (p.is_current) return p.projected_expense;
    return null;
  });
  const trendLine = points.map((p) =>
    p.is_forecast || p.is_current ? p.projected_expense : p.actual_expense
  );

  if (forecastChart) {
    forecastChart.destroy();
  }

  forecastChart = new Chart(document.getElementById('forecastChart'), {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: 'Фактические расходы',
          data: actualData,
          backgroundColor: points.map((p) =>
            p.is_current ? theme.accent : theme.accent + '66'
          ),
          borderRadius: 8,
          barPercentage: 0.6,
          order: 2,
        },
        {
          label: 'Прогноз / оценка',
          data: forecastData,
          backgroundColor: theme.green + '44',
          borderColor: theme.green,
          borderWidth: 2,
          borderDash: [5, 4],
          borderRadius: 8,
          barPercentage: 0.6,
          order: 3,
        },
        {
          type: 'line',
          label: 'Линия тренда',
          data: trendLine,
          borderColor: theme.prevColor,
          borderWidth: 2,
          borderDash: [4, 4],
          tension: 0.3,
          pointRadius: 3,
          fill: false,
          order: 1,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      animation: { duration: 400 },
      plugins: {
        legend: {
          display: true,
          position: 'top',
          align: 'end',
          labels: {
            color: theme.muted,
            boxWidth: 12,
            boxHeight: 12,
            font: { family: 'Manrope, sans-serif', size: 12, weight: '600' },
          },
        },
        tooltip: {
          callbacks: {
            label: (c) => {
              if (c.parsed.y === null || c.parsed.y === undefined) return null;
              return ` ${c.dataset.label}: ${fmtMoney(c.parsed.y)}`;
            },
          },
        },
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: theme.muted, font: { size: 11 } },
        },
        y: {
          beginAtZero: true,
          grid: { color: theme.grid },
          ticks: {
            color: theme.muted,
            font: { size: 11 },
            callback: (val) => (val >= 1000 ? Math.round(val / 1000) + 'k' : val),
          },
        },
      },
    },
  });
}
