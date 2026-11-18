const state = {
  view: 'overview',
  period: 'month',
  date: fmtDate(new Date()),
  statsType: 'expense',
  compMode: 'cumulative',
  filterType: '',
  filterCategoryId: null,
  filterAccountId: '',
  searchQuery: '',
  categories: [],
  accounts: [],
  formMode: 'create',
  editTxId: null,
  formType: 'expense',
  formCategory: null,
  manualCategoryChosen: false,
  selectedCatIcon: 'tag',
  lastComp: null,
  lastForecast: null,
  lastStats: [],
  csvParsedItems: [],
};

let reqId = 0;
let deleteId = null;
let searchTimer = null;
let suggestTimer = null;

const $ = (id) => document.getElementById(id);

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

const money = (n) => new Intl.NumberFormat('ru-RU').format(Math.round(n)) + ' ₸';
const catById = (id) => state.categories.find((c) => c.id === id);

function toast(msg, isError) {
  const t = el('div', 'toast' + (isError ? ' error' : ''), msg);
  $('toasts').append(t);
  setTimeout(() => t.remove(), 3500);
}

// --- Theme & Static Icons ---
function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  localStorage.setItem('spendwise_theme', theme);
  const btn = $('themeBtn');
  btn.replaceChildren(createSvgIcon(theme === 'dark' ? 'sun' : 'moon'));
  btn.title = theme === 'dark' ? 'Светлая тема' : 'Тёмная тема';
}

function initStaticIcons() {
  $('brandIcon').replaceChildren(createSvgIcon('wallet'));
  const exportBtn = $('exportCsvBtn');
  exportBtn.replaceChildren(createSvgIcon('download'), document.createTextNode('CSV'));
}

// --- Date Navigation ---
function shiftDate(dir) {
  const d = parseDate(state.date);
  if (state.period === 'day') d.setDate(d.getDate() + dir);
  else if (state.period === 'week') d.setDate(d.getDate() + 7 * dir);
  else {
    const day = d.getDate();
    d.setDate(1);
    d.setMonth(d.getMonth() + dir);
    const last = new Date(d.getFullYear(), d.getMonth() + 1, 0).getDate();
    d.setDate(Math.min(day, last));
  }
  state.date = fmtDate(d);
}

function periodLabel(s) {
  const a = parseDate(s.period_start);
  const b = parseDate(s.period_end);
  const clean = (t) => t.replace(/\s*г\.$/, '').replace(/\./g, '');
  if (state.period === 'day') {
    return clean(a.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' }));
  }
  if (state.period === 'week') {
    const o = { day: 'numeric', month: 'short' };
    return `${clean(a.toLocaleDateString('ru-RU', o))} – ${clean(b.toLocaleDateString('ru-RU', o))}`;
  }
  const t = clean(a.toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' }));
  return t[0].toUpperCase() + t.slice(1);
}

// --- Rendering Overview ---
function renderDelta(elNode, pct, invertGood) {
  if (pct === null || pct === undefined) {
    elNode.hidden = true;
    return;
  }
  const sign = pct > 0 ? '+' : '';
  elNode.textContent = `${sign}${pct}% к прошл.`;
  const isGood = invertGood ? pct <= 0 : pct >= 0;
  elNode.className = 'delta ' + (isGood ? 'good' : 'bad');
  elNode.hidden = false;
}

function renderComparisonMeta(comp) {
  const box = $('compMeta');
  box.replaceChildren();
  if (!comp) return;

  const curPill = el('span', 'meta-pill', `${comp.current_label}: ${money(comp.pace_current_total)}`);
  const prevPill = el('span', 'meta-pill', `${comp.previous_label}: ${money(comp.pace_previous_total)}`);
  box.append(curPill, prevPill);

  if (comp.delta_pct !== null && comp.delta_pct !== undefined) {
    const sign = comp.delta_pct > 0 ? '+' : '';
    const isGood = comp.type === 'expense' ? comp.delta_pct <= 0 : comp.delta_pct >= 0;
    const dPill = el(
      'span',
      'meta-pill ' + (isGood ? 'good' : 'bad'),
      `Динамика: ${sign}${comp.delta_pct}%`
    );
    box.append(dPill);
  }
}

function renderForecastSection(f) {
  if (!f) return;
  $('forecastTitle').textContent = `Прогноз расходов на ${f.target_month_label.toLowerCase()}`;
  $('forecastNextLabel').textContent = `Прогноз: ${f.target_month_label}`;
  $('forecastCurLabel').textContent = `Ожидание: ${f.current_month_label}`;

  $('forecastNext').textContent = money(f.forecast_next_month);
  $('forecastCurrentProj').textContent = money(f.current_month_projected);
  $('forecastCurrentActual').textContent = `Факт сейчас: ${money(f.current_month_actual)}`;
  $('forecastRange').textContent = `${money(f.forecast_low)} – ${money(f.forecast_high)}`;

  const savEl = $('forecastSavings');
  savEl.textContent = (f.expected_savings >= 0 ? '+' : '') + money(f.expected_savings);
  savEl.style.color = f.expected_savings >= 0 ? 'var(--green)' : 'var(--red)';
  $('forecastIncomeEst').textContent = `Ожидаемый доход: ${money(f.expected_income)}`;

  const trendSign = f.trend_percent > 0 ? '+' : '';
  $('forecastTrend').textContent =
    f.months_analyzed > 0
      ? `Тренд: ${trendSign}${f.trend_percent}% к среднему`
      : 'Нет истории за прошлые месяцы';

  const confMap = {
    high: 'Высокая точность',
    medium: 'Средняя точность',
    low: 'Мало данных',
  };
  const badge = $('forecastConfidence');
  badge.textContent = `${confMap[f.confidence] || f.confidence} (${f.months_analyzed} мес.)`;
  badge.className = `badge ${f.confidence}`;

  renderForecastChart(f, money);

  const catsBox = $('forecastCats');
  catsBox.replaceChildren();
  if (!f.by_category.length) {
    catsBox.append(el('p', 'muted', 'Недостаточно расходов по категориям для детализации.'));
  } else {
    f.by_category.slice(0, 6).forEach((c) => {
      const row = el('div', 'fcat-row');
      const top = el('div', 'fcat-top');
      const name = el('span', 'fcat-name');
      const dot = el('span', 'fcat-dot');
      dot.style.background = c.color;
      name.append(dot, document.createTextNode(c.name));

      const valText = c.budget_limit
        ? `${money(c.forecast_next_month)} / лимит ${money(c.budget_limit)}`
        : `${money(c.forecast_next_month)} (${c.share_pct}%)`;
      top.append(name, el('span', 'muted', valText));

      const track = el('div', 'progress-track');
      const fill = el('div', 'progress-fill');
      const pctWidth = c.budget_limit
        ? Math.min(100, Math.round((c.forecast_next_month / c.budget_limit) * 100))
        : Math.min(100, Math.round(c.share_pct));
      fill.style.width = `${pctWidth}%`;
      fill.style.background = c.budget_limit && c.forecast_next_month > c.budget_limit ? 'var(--red)' : c.color;
      track.append(fill);

      row.append(top, track);
      catsBox.append(row);
    });
  }

  const insightsBox = $('forecastInsights');
  insightsBox.replaceChildren();
  (f.insights || []).forEach((text) => {
    insightsBox.append(el('li', '', text));
  });
}

function renderList(txs) {
  const box = $('list');
  box.replaceChildren();

  const catChip = $('clearCatFilter');
  if (state.filterCategoryId !== null) {
    const c = catById(state.filterCategoryId);
    catChip.textContent = `Категория: ${c ? c.name : state.filterCategoryId} ✕`;
    catChip.hidden = false;
  } else {
    catChip.hidden = true;
  }

  if (!txs.length) {
    const msg =
      state.searchQuery || state.filterType || state.filterCategoryId || state.filterAccountId
        ? 'По заданным фильтрам операций не найдено'
        : 'Добавьте первую операцию — кнопка «+ Добавить» сверху';
    box.append(el('p', 'empty', msg));
    return;
  }

  let lastDate = null;
  txs.forEach((t) => {
    if (t.date !== lastDate) {
      lastDate = t.date;
      const h = parseDate(t.date).toLocaleDateString('ru-RU', {
        day: 'numeric',
        month: 'long',
        weekday: 'long',
      });
      box.append(el('div', 'day-head', h));
    }

    const row = el('div', 'tx');
    const ico = el('div', 'ico');
    const color = t.category_color || '#6C7CFF';
    ico.style.background = color + '24';
    ico.style.color = color;
    ico.append(createSvgIcon(t.is_transfer ? 'transfer' : t.category_icon || 'tag'));

    const info = el('div', 'info');
    const catRow = el('div', 'cat-row');
    catRow.append(el('span', 'cat', t.is_transfer ? 'Перевод' : t.category_name));
    if (t.account_name) {
      catRow.append(el('span', 'acc-tag', t.account_name));
    }
    info.append(catRow);
    if (t.note) info.append(el('div', 'note', t.note));

    const sign = t.type === 'income' ? '+' : '−';
    const amt = el(
      'div',
      'amt ' + (t.type === 'income' ? 'plus' : 'minus'),
      sign + ' ' + money(t.amount)
    );

    const actions = el('div', 'tx-actions');
    if (!t.is_transfer) {
      const editBtn = el('button', 'act-btn');
      editBtn.type = 'button';
      editBtn.setAttribute('aria-label', 'Редактировать операцию');
      editBtn.title = 'Редактировать';
      editBtn.append(createSvgIcon('edit'));
      editBtn.addEventListener('click', () => openEditModal(t));
      actions.append(editBtn);
    }

    const delBtn = el('button', 'act-btn del');
    delBtn.type = 'button';
    delBtn.setAttribute('aria-label', 'Удалить операцию');
    delBtn.title = 'Удалить';
    delBtn.append(createSvgIcon('trash'));
    delBtn.addEventListener('click', () => {
      deleteId = t.id;
      $('confirm').hidden = false;
    });
    actions.append(delBtn);

    row.append(ico, info, amt, actions);
    box.append(row);
  });
}

function populateAccountSelects() {
  const opts = state.accounts;
  const filterSel = $('accountFilter');
  const prevVal = state.filterAccountId;
  filterSel.replaceChildren(new Option('Все счета', ''));
  opts.forEach((a) => filterSel.append(new Option(a.name, String(a.id))));
  filterSel.value = prevVal;

  const modalSel = $('accountSelect');
  modalSel.replaceChildren();
  opts.forEach((a) => modalSel.append(new Option(a.name, String(a.id))));

  const trFrom = $('trFrom');
  const trTo = $('trTo');
  trFrom.replaceChildren();
  trTo.replaceChildren();
  opts.forEach((a) => {
    trFrom.append(new Option(`${a.name} (${money(a.current_balance)})`, String(a.id)));
    trTo.append(new Option(`${a.name} (${money(a.current_balance)})`, String(a.id)));
  });
  if (opts.length >= 2) trTo.selectedIndex = 1;
}

function onDoughnutCategorySelect(catId) {
  state.filterCategoryId = state.filterCategoryId === catId ? null : catId;
  refreshTransactionsOnly();
  renderDoughnutChart(state.lastStats, money, state.filterCategoryId, onDoughnutCategorySelect);
}

async function refreshOverview() {
  const id = ++reqId;
  document.body.classList.add('loading');
  try {
    const txParams = {
      period: state.period,
      date: state.date,
      type: state.filterType,
      category_id: state.filterCategoryId,
      account_id: state.filterAccountId,
      q: state.searchQuery,
    };

    const [txs, sum, stats, comp, forecast] = await Promise.all([
      getTransactions(txParams),
      getSummary(state.period, state.date),
      getStatsByCategory(state.period, state.date, state.statsType),
      getPeriodComparison(state.period, state.date, state.statsType),
      getExpenseForecast(state.date),
    ]);
    if (id !== reqId) return;

    state.lastStats = stats;
    state.lastComp = comp;
    state.lastForecast = forecast;

    $('income').textContent = money(sum.income);
    $('expense').textContent = money(sum.expense);
    $('balance').textContent = money(sum.balance);
    $('periodLabel').textContent = periodLabel(sum);

    renderDelta($('incomeDelta'), sum.income_change_pct, false);
    renderDelta($('expenseDelta'), sum.expense_change_pct, true);

    const safePill = $('safeSpendPill');
    if (sum.safe_daily_spend !== null && sum.safe_daily_spend !== undefined) {
      safePill.textContent = `Лимит в день: ${money(sum.safe_daily_spend)}`;
      safePill.hidden = false;
    } else {
      safePill.hidden = true;
    }

    renderDoughnutChart(stats, money, state.filterCategoryId, onDoughnutCategorySelect);

    renderComparisonMeta(comp);
    renderComparisonChart(comp, state.compMode, money);
    renderForecastSection(forecast);
    renderList(txs);
  } catch (e) {
    if (id === reqId) toast(e.message, true);
  } finally {
    if (id === reqId) document.body.classList.remove('loading');
  }
}

async function refreshTransactionsOnly() {
  try {
    const txs = await getTransactions({
      period: state.period,
      date: state.date,
      type: state.filterType,
      category_id: state.filterCategoryId,
      account_id: state.filterAccountId,
      q: state.searchQuery,
    });
    renderList(txs);
  } catch (e) {
    toast(e.message, true);
  }
}

// --- Planning Tab ---
async function refreshPlanning() {
  const monthKey = fmtMonthKey(state.date);
  $('budgetMonthLabel').textContent = monthKey;
  try {
    const [budgets, goals, recurring] = await Promise.all([
      getBudgets(monthKey),
      getGoals(),
      getRecurringRules(monthKey),
    ]);
    renderBudgets(budgets);
    renderGoals(goals);
    renderRecurring(recurring);
    populateRecurringCategories();
  } catch (e) {
    toast(e.message, true);
  }
}

function renderBudgets(data) {
  const statsBox = $('budgetOverviewStats');
  statsBox.replaceChildren(
    el('span', 'meta-pill', `Общий лимит: ${money(data.total_limit)}`),
    el('span', 'meta-pill', `Потрачено: ${money(data.total_spent)}`)
  );
  if (data.safe_daily_spend !== null) {
    statsBox.append(
      el('span', 'meta-pill good', `Можно тратить в день: ${money(data.safe_daily_spend)}`)
    );
  }

  const list = $('budgetsList');
  list.replaceChildren();
  data.items.forEach((b) => {
    const row = el('div', 'budget-row');
    const top = el('div', 'budget-top');

    const cat = el('div', 'budget-cat');
    const ico = el('span', 'ico');
    ico.style.color = b.category_color;
    ico.append(createSvgIcon(b.category_icon));
    const spentText = b.limit_amount
      ? `${money(b.spent)} из ${money(b.limit_amount)} (${b.percent}%)`
      : `Потрачено: ${money(b.spent)} (лимит не задан)`;
    cat.append(ico, el('span', '', b.category_name), el('span', 'muted', spentText));

    const form = el('form', 'budget-input-group');
    const inp = el('input');
    inp.type = 'number';
    inp.min = '0';
    inp.placeholder = 'Лимит, ₸';
    inp.value = b.limit_amount ?? '';
    const saveBtn = el('button', 'btn btn-sm', 'Сохранить');
    saveBtn.type = 'submit';
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const val = inp.value.trim() === '' ? 0 : Number(inp.value);
      try {
        await upsertBudget({ category_id: b.category_id, month: data.month, limit_amount: val });
        toast(val > 0 ? 'Бюджет сохранён' : 'Лимит сброшен');
        refreshPlanning();
      } catch (err) {
        toast(err.message, true);
      }
    });
    form.append(inp, saveBtn);
    top.append(cat, form);
    row.append(top);

    if (b.limit_amount) {
      const track = el('div', 'progress-track');
      const fill = el('div', `progress-fill ${b.status}`);
      fill.style.width = `${Math.min(100, b.percent || 0)}%`;
      track.append(fill);
      row.append(track);
    }

    list.append(row);
  });
}

function renderGoals(goals) {
  const box = $('goalsList');
  box.replaceChildren();
  if (!goals.length) {
    box.append(el('p', 'empty', 'Пока нет целей накоплений'));
    return;
  }
  goals.forEach((g) => {
    const card = el('div', 'item-card');
    const row = el('div', 'item-row');
    const title = el('div', 'item-title');
    const ico = el('span');
    ico.style.color = g.color;
    ico.append(createSvgIcon(g.icon || 'target'));
    title.append(ico, document.createTextNode(g.name));

    const actions = el('div', 'item-actions');
    [5000, 10000].forEach((step) => {
      const addBtn = el('button', 'btn btn-sm', `+${step / 1000}k`);
      addBtn.type = 'button';
      addBtn.addEventListener('click', async () => {
        try {
          await contributeGoal(g.id, step);
          toast(`+${money(step)} к цели «${g.name}»`);
          refreshPlanning();
        } catch (err) {
          toast(err.message, true);
        }
      });
      actions.append(addBtn);
    });
    const delBtn = el('button', 'act-btn del');
    delBtn.type = 'button';
    delBtn.append(createSvgIcon('trash'));
    delBtn.addEventListener('click', async () => {
      try {
        await deleteGoal(g.id);
        toast('Цель удалена');
        refreshPlanning();
      } catch (err) {
        toast(err.message, true);
      }
    });
    actions.append(delBtn);
    row.append(title, actions);

    const meta = el(
      'div',
      'muted',
      `${money(g.current_amount)} из ${money(g.target_amount)} (${g.percent}%)` +
        (g.deadline ? ` · до ${g.deadline}` : '')
    );
    const track = el('div', 'progress-track');
    const fill = el('div', 'progress-fill ' + (g.is_completed ? 'ok' : ''));
    fill.style.width = `${g.percent}%`;
    fill.style.background = g.is_completed ? 'var(--green)' : g.color;
    track.append(fill);

    card.append(row, meta, track);
    box.append(card);
  });
}

function populateRecurringCategories() {
  const type = $('recType').value;
  const sel = $('recCategory');
  sel.replaceChildren();
  state.categories
    .filter((c) => c.type === type)
    .forEach((c) => sel.append(new Option(c.name, String(c.id))));
}

function renderRecurring(rules) {
  const box = $('recurringList');
  box.replaceChildren();
  if (!rules.length) {
    box.append(el('p', 'empty', 'Нет регулярных операций'));
    return;
  }
  rules.forEach((r) => {
    const card = el('div', 'item-card');
    const row = el('div', 'item-row');
    const title = el('div', 'item-title');
    const ico = el('span');
    ico.style.color = r.category_color;
    ico.append(createSvgIcon(r.category_icon));
    title.append(ico, document.createTextNode(`${r.note || r.category_name} (${r.day_of_month}-го числа)`));

    const actions = el('div', 'item-actions');
    const sign = r.type === 'income' ? '+' : '−';
    actions.append(el('strong', '', `${sign} ${money(r.amount)}`));

    const statusBadge = el(
      'span',
      'badge ' + (r.applied_current_month ? 'high' : 'low'),
      r.applied_current_month ? 'Начислено' : 'Ожидает'
    );
    actions.append(statusBadge);

    const toggleBtn = el('button', 'btn btn-sm', r.is_active ? 'Пауза' : 'Включить');
    toggleBtn.type = 'button';
    toggleBtn.addEventListener('click', async () => {
      try {
        await updateRecurringRule(r.id, { is_active: !r.is_active });
        refreshPlanning();
      } catch (err) {
        toast(err.message, true);
      }
    });
    actions.append(toggleBtn);

    const delBtn = el('button', 'act-btn del');
    delBtn.type = 'button';
    delBtn.append(createSvgIcon('trash'));
    delBtn.addEventListener('click', async () => {
      try {
        await deleteRecurringRule(r.id);
        toast('Правило удалено');
        refreshPlanning();
      } catch (err) {
        toast(err.message, true);
      }
    });
    actions.append(delBtn);

    row.append(title, actions);
    card.append(row);
    box.append(card);
  });
}

// --- Manage Tab ---
async function refreshManage() {
  try {
    const [accounts, categories] = await Promise.all([getAccounts(), getCategories()]);
    state.accounts = accounts;
    state.categories = categories;
    populateAccountSelects();
    renderAccountsManage(accounts);
    renderCategoriesManage(categories);
    renderCatIconPicker();
  } catch (e) {
    toast(e.message, true);
  }
}

function renderAccountsManage(accounts) {
  const box = $('accountsList');
  box.replaceChildren();
  accounts.forEach((a) => {
    const card = el('div', 'account-card');
    const top = el('div', 'item-row');
    const title = el('div', 'item-title');
    const ico = el('span');
    ico.style.color = a.color;
    ico.append(createSvgIcon(a.icon || 'card'));
    title.append(ico, document.createTextNode(a.name));
    top.append(title);

    if (!a.is_default) {
      const delBtn = el('button', 'act-btn del');
      delBtn.type = 'button';
      delBtn.append(createSvgIcon('trash'));
      delBtn.addEventListener('click', async () => {
        try {
          await deleteAccount(a.id);
          toast('Счёт удалён');
          refreshManage();
        } catch (err) {
          toast(err.message, true);
        }
      });
      top.append(delBtn);
    }

    const bal = el('strong', '', money(a.current_balance));
    const typeMap = { card: 'Банковская карта', cash: 'Наличные', savings: 'Копилка' };
    card.append(top, bal, el('span', 'muted', typeMap[a.type] || a.type));
    box.append(card);
  });
}

function renderCategoriesManage(categories) {
  const box = $('categoriesList');
  box.replaceChildren();
  categories.forEach((c) => {
    const card = el('div', 'item-card');
    const row = el('div', 'item-row');
    const title = el('div', 'item-title');
    const ico = el('span');
    ico.style.color = c.color;
    ico.append(createSvgIcon(c.icon || 'tag'));
    title.append(
      ico,
      document.createTextNode(c.name),
      el('span', 'acc-tag', c.type === 'income' ? 'Доход' : 'Расход')
    );

    row.append(title);
    if (!c.is_default) {
      const delBtn = el('button', 'act-btn del');
      delBtn.type = 'button';
      delBtn.append(createSvgIcon('trash'));
      delBtn.addEventListener('click', async () => {
        try {
          const fallback = state.categories.find((x) => x.is_default && x.type === c.type);
          await deleteCategory(c.id, fallback ? fallback.id : undefined);
          toast('Категория удалена');
          refreshManage();
        } catch (err) {
          toast(err.message, true);
        }
      });
      row.append(delBtn);
    } else {
      row.append(el('span', 'muted', 'Базовая'));
    }

    card.append(row);
    box.append(card);
  });
}

function renderCatIconPicker() {
  const box = $('catIconPicker');
  box.replaceChildren();
  CATEGORY_ICON_CHOICES.forEach((iconName) => {
    const btn = el('button', 'icon-opt' + (state.selectedCatIcon === iconName ? ' active' : ''));
    btn.type = 'button';
    btn.title = iconName;
    btn.append(createSvgIcon(iconName));
    btn.addEventListener('click', () => {
      state.selectedCatIcon = iconName;
      renderCatIconPicker();
    });
    box.append(btn);
  });
}

// --- CSV Parser ---
function normalizeCsvDate(raw) {
  const s = raw.trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s;
  const dm = s.match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
  if (dm) return `${dm[3]}-${dm[2]}-${dm[1]}`;
  return null;
}

function parseCsvLines(text) {
  const lines = text
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean);
  const parsed = [];

  const expFallback = state.categories.find((c) => c.type === 'expense');
  const incFallback = state.categories.find((c) => c.type === 'income');

  lines.forEach((line, idx) => {
    const sep = line.includes(';') ? ';' : line.includes('\t') ? '\t' : ',';
    const cols = line.split(sep).map((c) => c.trim().replace(/^"|"$/g, ''));
    if (cols.length < 3) return;
    if (idx === 0 && /дата|date/i.test(cols[0])) return;

    const dateVal = normalizeCsvDate(cols[0]);
    if (!dateVal) return;

    let txType = null;
    let amtIdx = 2;
    let catIdx = 3;
    let noteIdx = 4;

    if (/^(income|доход)$/i.test(cols[1])) {
      txType = 'income';
    } else if (/^(expense|расход)$/i.test(cols[1])) {
      txType = 'expense';
    } else if (/^[+-]?\d+/.test(cols[1].replace(/\s/g, ''))) {
      amtIdx = 1;
      catIdx = 2;
      noteIdx = 3;
    }

    const rawAmtStr = (cols[amtIdx] || '').replace(/\s+/g, '').replace(',', '.');
    const numAmt = Number(rawAmtStr);
    if (!Number.isFinite(numAmt) || numAmt === 0) return;

    if (!txType) txType = numAmt < 0 ? 'expense' : 'income';
    const amount = Math.round(Math.abs(numAmt));
    const catName = (cols[catIdx] || '').toLowerCase();
    const note = (cols[noteIdx] || '').slice(0, 100);

    let matchedCat = state.categories.find(
      (c) => c.type === txType && c.name.toLowerCase() === catName
    );
    if (!matchedCat) {
      matchedCat = txType === 'income' ? incFallback : expFallback;
    }
    if (!matchedCat) return;

    parsed.push({
      date: dateVal,
      type: txType,
      amount,
      category_id: matchedCat.id,
      category_name: matchedCat.name,
      note,
    });
  });

  return parsed;
}

function renderCsvPreview(items) {
  const box = $('csvPreview');
  box.replaceChildren();
  const confirmBtn = $('confirmImportBtn');

  if (!items.length) {
    confirmBtn.hidden = true;
    box.append(el('p', 'muted', 'Не удалось распознать корректные строки. Проверьте формат даты (ГГГГ-ММ-ДД) и суммы.'));
    return;
  }

  confirmBtn.hidden = false;
  confirmBtn.textContent = `Импортировать (${items.length})`;

  const table = el('table', 'csv-table');
  const thead = document.createElement('thead');
  const hRow = document.createElement('tr');
  ['Дата', 'Тип', 'Категория', 'Сумма', 'Заметка'].forEach((h) =>
    hRow.append(el('th', '', h))
  );
  thead.append(hRow);

  const tbody = document.createElement('tbody');
  items.slice(0, 30).forEach((it) => {
    const tr = document.createElement('tr');
    tr.append(
      el('td', '', it.date),
      el('td', '', it.type === 'income' ? 'Доход' : 'Расход'),
      el('td', '', it.category_name),
      el('td', '', money(it.amount)),
      el('td', '', it.note || '—')
    );
    tbody.append(tr);
  });

  table.append(thead, tbody);
  box.append(table);
}

// --- Transaction Modal (Create & Edit) ---
function renderChips() {
  const box = $('chips');
  box.replaceChildren();
  state.categories
    .filter((c) => c.type === state.formType)
    .forEach((c) => {
      const b = el('button', 'chip' + (c.id === state.formCategory ? ' active' : ''));
      b.type = 'button';
      b.append(createSvgIcon(c.icon || 'tag'), document.createTextNode(c.name));
      if (c.id === state.formCategory) b.style.borderColor = c.color;
      b.addEventListener('click', () => {
        state.formCategory = c.id;
        state.manualCategoryChosen = true;
        $('suggestPill').hidden = true;
        box.classList.remove('invalid');
        renderChips();
      });
      box.append(b);
    });
}

function setFormType(type, keepCategory = false) {
  state.formType = type;
  if (!keepCategory) state.formCategory = null;
  document
    .querySelectorAll('#typeTabs button')
    .forEach((b) => b.classList.toggle('active', b.dataset.type === type));
  renderChips();
}

function openCreateModal() {
  state.formMode = 'create';
  state.editTxId = null;
  state.manualCategoryChosen = false;
  $('modalTitle').textContent = 'Новая операция';
  $('submitTxBtn').textContent = 'Сохранить';
  $('form').reset();
  $('dateInput').value = fmtDate(new Date());
  $('suggestPill').hidden = true;
  if (state.accounts.length) $('accountSelect').value = String(state.accounts[0].id);
  document.querySelectorAll('.invalid').forEach((e) => e.classList.remove('invalid'));
  setFormType('expense');
  $('modal').hidden = false;
  $('amount').focus();
}

function openEditModal(tx) {
  state.formMode = 'edit';
  state.editTxId = tx.id;
  state.manualCategoryChosen = true;
  $('modalTitle').textContent = 'Редактировать операцию';
  $('submitTxBtn').textContent = 'Обновить';
  $('form').reset();
  $('amount').value = String(tx.amount);
  $('note').value = tx.note || '';
  $('dateInput').value = tx.date;
  $('suggestPill').hidden = true;
  if (tx.account_id) $('accountSelect').value = String(tx.account_id);
  document.querySelectorAll('.invalid').forEach((e) => e.classList.remove('invalid'));
  state.formCategory = tx.category_id;
  setFormType(tx.type, true);
  $('modal').hidden = false;
  $('amount').focus();
}

const closeModal = () => {
  $('modal').hidden = true;
};

async function handleNoteSuggest() {
  const noteVal = $('note').value.trim();
  const pill = $('suggestPill');
  if (noteVal.length < 2) {
    pill.hidden = true;
    return;
  }
  try {
    const res = await suggestCategory(noteVal, state.formType);
    if (res && res.category_id && res.category_id !== state.formCategory) {
      if (!state.manualCategoryChosen && state.formMode === 'create') {
        state.formCategory = res.category_id;
        renderChips();
      } else {
        pill.textContent = `Подсказка: ${res.category_name}`;
        pill.dataset.catId = String(res.category_id);
        pill.hidden = false;
      }
    } else {
      pill.hidden = true;
    }
  } catch {}
}

async function submitForm(e) {
  e.preventDefault();
  const raw = $('amount').value.trim();
  const amount = /^\d+$/.test(raw) ? Number(raw) : NaN;
  const dateVal = $('dateInput').value;
  let ok = true;
  const mark = (node, bad) => {
    node.classList.toggle('invalid', bad);
    if (bad) ok = false;
  };
  mark($('amount'), !(amount > 0));
  mark($('chips'), state.formCategory === null);
  mark($('dateInput'), !dateVal);
  if (!ok) return;

  const payload = {
    type: state.formType,
    amount,
    category_id: state.formCategory,
    account_id: $('accountSelect').value ? Number($('accountSelect').value) : null,
    note: $('note').value.trim(),
    date: dateVal,
  };

  try {
    if (state.formMode === 'edit' && state.editTxId !== null) {
      await updateTransaction(state.editTxId, payload);
      toast('Операция обновлена');
    } else {
      await addTransaction(payload);
      toast(state.formType === 'income' ? 'Доход добавлен' : 'Расход добавлен');
    }
    closeModal();
    await loadAccounts();
    refreshCurrentView();
  } catch (err) {
    toast(err.message, true);
  }
}

async function confirmDelete() {
  const id = deleteId;
  $('confirm').hidden = true;
  try {
    await deleteTransaction(id);
    toast('Операция удалена');
    await loadAccounts();
    refreshCurrentView();
  } catch (err) {
    toast(err.message, true);
  }
}

async function loadAccounts() {
  try {
    state.accounts = await getAccounts();
    populateAccountSelects();
  } catch {}
}

function switchView(viewName) {
  state.view = viewName;
  document.querySelectorAll('#viewTabs button').forEach((b) =>
    b.classList.toggle('active', b.dataset.view === viewName)
  );
  ['overview', 'planning', 'manage'].forEach((v) => {
    $(`view-${v}`).hidden = v !== viewName;
  });
  refreshCurrentView();
}

function refreshCurrentView() {
  if (state.view === 'overview') refreshOverview();
  else if (state.view === 'planning') refreshPlanning();
  else refreshManage();
}

function bind() {
  $('themeBtn').addEventListener('click', () => {
    const cur = document.documentElement.getAttribute('data-theme') || 'dark';
    applyTheme(cur === 'dark' ? 'light' : 'dark');
    if (state.view === 'overview') {
      renderDoughnutChart(state.lastStats, money, state.filterCategoryId, onDoughnutCategorySelect);
      renderComparisonChart(state.lastComp, state.compMode, money);
      renderForecastChart(state.lastForecast, money);
    }
  });

  $('viewTabs').addEventListener('click', (e) => {
    const b = e.target.closest('button');
    if (b) switchView(b.dataset.view);
  });

  $('addBtn').addEventListener('click', openCreateModal);
  $('closeModal').addEventListener('click', closeModal);
  $('form').addEventListener('submit', submitForm);
  $('amount').addEventListener('input', (e) => {
    e.target.value = e.target.value.replace(/\D/g, '');
    e.target.classList.remove('invalid');
  });
  $('dateInput').addEventListener('input', (e) => e.target.classList.remove('invalid'));
  $('note').addEventListener('input', () => {
    clearTimeout(suggestTimer);
    suggestTimer = setTimeout(handleNoteSuggest, 220);
  });
  $('suggestPill').addEventListener('click', () => {
    const cid = Number($('suggestPill').dataset.catId);
    if (cid) {
      state.formCategory = cid;
      state.manualCategoryChosen = true;
      $('suggestPill').hidden = true;
      renderChips();
    }
  });

  $('typeTabs').addEventListener('click', (e) => {
    const b = e.target.closest('button');
    if (b) {
      state.manualCategoryChosen = false;
      setFormType(b.dataset.type);
    }
  });

  // Overview period & filters
  $('tabs').addEventListener('click', (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    state.period = b.dataset.period;
    document.querySelectorAll('#tabs button').forEach((x) => x.classList.toggle('active', x === b));
    refreshOverview();
  });
  $('prevBtn').addEventListener('click', () => {
    shiftDate(-1);
    refreshOverview();
  });
  $('nextBtn').addEventListener('click', () => {
    shiftDate(1);
    refreshOverview();
  });
  $('todayBtn').addEventListener('click', () => {
    state.date = fmtDate(new Date());
    refreshOverview();
  });

  $('statsTypeTabs').addEventListener('click', (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    state.statsType = b.dataset.type;
    document
      .querySelectorAll('#statsTypeTabs button')
      .forEach((x) => x.classList.toggle('active', x === b));
    refreshOverview();
  });

  $('compModeTabs').addEventListener('click', (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    state.compMode = b.dataset.mode;
    document
      .querySelectorAll('#compModeTabs button')
      .forEach((x) => x.classList.toggle('active', x === b));
    renderComparisonChart(state.lastComp, state.compMode, money);
  });

  $('listTypeTabs').addEventListener('click', (e) => {
    const b = e.target.closest('button');
    if (!b) return;
    state.filterType = b.dataset.type;
    document
      .querySelectorAll('#listTypeTabs button')
      .forEach((x) => x.classList.toggle('active', x === b));
    refreshTransactionsOnly();
  });

  $('accountFilter').addEventListener('change', (e) => {
    state.filterAccountId = e.target.value;
    refreshTransactionsOnly();
  });

  $('searchInput').addEventListener('input', (e) => {
    state.searchQuery = e.target.value;
    clearTimeout(searchTimer);
    searchTimer = setTimeout(refreshTransactionsOnly, 240);
  });

  $('clearCatFilter').addEventListener('click', () => {
    state.filterCategoryId = null;
    refreshTransactionsOnly();
    renderDoughnutChart(state.lastStats, money, null, onDoughnutCategorySelect);
  });

  $('exportCsvBtn').addEventListener('click', () => {
    window.location.href = exportTransactionsUrl({
      period: state.period,
      date: state.date,
      type: state.filterType,
      category_id: state.filterCategoryId,
      account_id: state.filterAccountId,
      q: state.searchQuery,
    });
  });

  // Planning forms
  $('goalForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    try {
      await createGoal({
        name: $('goalName').value.trim(),
        target_amount: Number($('goalTarget').value),
        deadline: $('goalDeadline').value || null,
      });
      $('goalForm').reset();
      toast('Цель создана');
      refreshPlanning();
    } catch (err) {
      toast(err.message, true);
    }
  });

  $('recType').addEventListener('change', populateRecurringCategories);
  $('recurringForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    try {
      await createRecurringRule({
        type: $('recType').value,
        category_id: Number($('recCategory').value),
        amount: Number($('recAmount').value),
        day_of_month: Number($('recDay').value) || 1,
        note: $('recNote').value.trim() || null,
      });
      $('recurringForm').reset();
      $('recDay').value = '1';
      populateRecurringCategories();
      toast('Регулярная операция добавлена');
      refreshPlanning();
    } catch (err) {
      toast(err.message, true);
    }
  });

  $('applyRecurringBtn').addEventListener('click', async () => {
    try {
      const res = await applyRecurringRules(fmtMonthKey(state.date));
      toast(
        res.created_count > 0
          ? `Начислено операций: ${res.created_count}`
          : 'Все регулярные операции за этот месяц уже начислены'
      );
      await loadAccounts();
      refreshPlanning();
    } catch (err) {
      toast(err.message, true);
    }
  });

  // Manage forms
  $('accountForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    try {
      await createAccount({
        name: $('accName').value.trim(),
        type: $('accType').value,
        initial_balance: Number($('accInitial').value || 0),
        icon: $('accType').value === 'cash' ? 'cash' : 'card',
      });
      $('accountForm').reset();
      toast('Счёт добавлен');
      refreshManage();
    } catch (err) {
      toast(err.message, true);
    }
  });

  $('openTransferBtn').addEventListener('click', () => {
    if (state.accounts.length < 2) {
      toast('Создайте хотя бы два счёта для перевода', true);
      return;
    }
    $('trDate').value = fmtDate(new Date());
    $('transferModal').hidden = false;
  });
  $('closeTransferModal').addEventListener('click', () => {
    $('transferModal').hidden = true;
  });
  $('transferForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    try {
      await transferBetweenAccounts({
        from_account_id: Number($('trFrom').value),
        to_account_id: Number($('trTo').value),
        amount: Number($('trAmount').value),
        date: $('trDate').value,
        note: $('trNote').value.trim() || null,
      });
      $('transferForm').reset();
      $('transferModal').hidden = true;
      toast('Перевод выполнен');
      refreshManage();
    } catch (err) {
      toast(err.message, true);
    }
  });

  $('categoryForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    try {
      await createCategory({
        name: $('catName').value.trim(),
        type: $('catType').value,
        color: $('catColor').value,
        icon: state.selectedCatIcon,
      });
      $('categoryForm').reset();
      $('catColor').value = '#6C7CFF';
      toast('Категория создана');
      refreshManage();
    } catch (err) {
      toast(err.message, true);
    }
  });

  // CSV Import
  $('csvFileInput').addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      $('csvPasteInput').value = reader.result || '';
      state.csvParsedItems = parseCsvLines($('csvPasteInput').value);
      renderCsvPreview(state.csvParsedItems);
    };
    reader.readAsText(file, 'utf-8');
  });

  $('parseCsvBtn').addEventListener('click', () => {
    state.csvParsedItems = parseCsvLines($('csvPasteInput').value);
    renderCsvPreview(state.csvParsedItems);
  });

  $('confirmImportBtn').addEventListener('click', async () => {
    if (!state.csvParsedItems.length) return;
    try {
      const payload = state.csvParsedItems.map(({ date, type, amount, category_id, note }) => ({
        date,
        type,
        amount,
        category_id,
        note,
      }));
      const res = await importTransactions(payload);
      toast(`Импортировано: ${res.imported}, пропущено: ${res.skipped}`);
      $('csvPasteInput').value = '';
      $('csvPreview').replaceChildren();
      $('confirmImportBtn').hidden = true;
      state.csvParsedItems = [];
      await loadAccounts();
    } catch (err) {
      toast(err.message, true);
    }
  });

  // Delete modal & keyboard shortcuts
  $('cancelDel').addEventListener('click', () => {
    $('confirm').hidden = true;
  });
  $('okDel').addEventListener('click', confirmDelete);
  [$('modal'), $('confirm'), $('transferModal')].forEach((o) =>
    o.addEventListener('click', (e) => {
      if (e.target === o) o.hidden = true;
    })
  );

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      $('modal').hidden = true;
      $('confirm').hidden = true;
      $('transferModal').hidden = true;
      return;
    }
    const tag = (e.target && e.target.tagName) || '';
    if (['INPUT', 'TEXTAREA', 'SELECT'].includes(tag)) return;
    if (!$('modal').hidden || !$('confirm').hidden || !$('transferModal').hidden) return;

    if (e.key.toLowerCase() === 'n') {
      e.preventDefault();
      openCreateModal();
    } else if (e.key.toLowerCase() === 't' && state.view === 'overview') {
      state.date = fmtDate(new Date());
      refreshOverview();
    } else if (e.key === 'ArrowLeft' && state.view === 'overview') {
      shiftDate(-1);
      refreshOverview();
    } else if (e.key === 'ArrowRight' && state.view === 'overview') {
      shiftDate(1);
      refreshOverview();
    }
  });
}

(async function init() {
  applyTheme(localStorage.getItem('spendwise_theme') || 'dark');
  initStaticIcons();
  bind();
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  }
  try {
    const [cats, accs] = await Promise.all([getCategories(), getAccounts()]);
    state.categories = cats;
    state.accounts = accs;
    populateAccountSelects();
  } catch (e) {
    toast(e.message, true);
  }
  refreshOverview();
})();
