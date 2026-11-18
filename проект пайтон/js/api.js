const API_URL =
  typeof window !== 'undefined' &&
  (window.location.protocol === 'file:' ||
    (window.location.port && window.location.port !== '8000'))
    ? 'http://127.0.0.1:8000/api'
    : '/api';

const pad = (n) => String(n).padStart(2, '0');
const fmtDate = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const fmtMonthKey = (s) => s.slice(0, 7);
const parseDate = (s) => {
  const [y, m, d] = s.split('-').map(Number);
  return new Date(y, m - 1, d);
};

async function request(method, path, body) {
  let res;
  try {
    res = await fetch(API_URL + path, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new Error('Не удалось связаться с сервером');
  }

  if (res.status === 204) return null;

  let data = null;
  try {
    data = await res.json();
  } catch {}

  if (!res.ok) {
    const detail = data && data.detail;
    throw new Error(typeof detail === 'string' ? detail : `Ошибка сервера (${res.status})`);
  }
  return data;
}

const qs = (params) => {
  const clean = {};
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== '') clean[k] = String(v);
  });
  const str = new URLSearchParams(clean).toString();
  return str ? '?' + str : '';
};

// Categories
const getCategories = () => request('GET', '/categories');
const createCategory = (data) => request('POST', '/categories', data);
const updateCategory = (id, data) => request('PATCH', `/categories/${id}`, data);
const deleteCategory = (id, reassignTo) =>
  request('DELETE', `/categories/${id}` + qs({ reassign_to: reassignTo }));

// Accounts / Wallets
const getAccounts = () => request('GET', '/accounts');
const createAccount = (data) => request('POST', '/accounts', data);
const updateAccount = (id, data) => request('PATCH', `/accounts/${id}`, data);
const deleteAccount = (id) => request('DELETE', `/accounts/${id}`);
const transferBetweenAccounts = (data) => request('POST', '/accounts/transfer', data);

// Transactions
const getTransactions = (params) => request('GET', '/transactions' + qs(params));
const addTransaction = (data) => request('POST', '/transactions', data);
const updateTransaction = (id, data) => request('PATCH', `/transactions/${id}`, data);
const deleteTransaction = (id) => request('DELETE', `/transactions/${id}`);
const importTransactions = (items) => request('POST', '/transactions/import', { items });
const suggestCategory = (note, type) =>
  request('GET', '/transactions/suggest-category' + qs({ note, type }));
const exportTransactionsUrl = (params) => API_URL + '/transactions/export' + qs(params);

// Stats & Forecast
const getSummary = (period, date) => request('GET', '/summary' + qs({ period, date }));
const getStatsByCategory = (period, date, type = 'expense') =>
  request('GET', '/stats/by-category' + qs({ period, date, type }));
const getPeriodComparison = (period, date, type = 'expense') =>
  request('GET', '/stats/comparison' + qs({ period, date, type }));
const getExpenseForecast = (date) => request('GET', '/stats/forecast' + qs({ date }));

// Budgets
const getBudgets = (month) => request('GET', '/budgets' + qs({ month }));
const upsertBudget = (data) => request('PUT', '/budgets', data);
const deleteBudget = (id) => request('DELETE', `/budgets/${id}`);

// Recurring
const getRecurringRules = (month) => request('GET', '/recurring' + qs({ month }));
const createRecurringRule = (data) => request('POST', '/recurring', data);
const updateRecurringRule = (id, data) => request('PATCH', `/recurring/${id}`, data);
const deleteRecurringRule = (id) => request('DELETE', `/recurring/${id}`);
const applyRecurringRules = (month) => request('POST', '/recurring/apply' + qs({ month }));

// Goals
const getGoals = () => request('GET', '/goals');
const createGoal = (data) => request('POST', '/goals', data);
const updateGoal = (id, data) => request('PATCH', `/goals/${id}`, data);
const contributeGoal = (id, delta) => request('POST', `/goals/${id}/contribute`, { delta });
const deleteGoal = (id) => request('DELETE', `/goals/${id}`);
