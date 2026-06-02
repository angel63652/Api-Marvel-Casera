/* ============================================================
   WMS Almacén - Shared App Utilities
   ============================================================ */

'use strict';

/* ============================================================
   API Helper
   ============================================================ */
let refreshInFlight = null;

async function api(method, path, body = null) {
  const result = await apiWithMeta(method, path, body);
  return result?.data;
}

async function apiWithMeta(method, path, body = null, retryingAfterRefresh = false) {
  const token = localStorage.getItem('wms_token');
  const headers = { 'Content-Type': 'application/json', 'Accept': 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;

  const opts = {
    method: method.toUpperCase(),
    headers,
    credentials: 'same-origin',
  };
  if (body !== null) opts.body = JSON.stringify(body);

  try {
    const res = await fetch(`/api/v1${path}`, opts);

    if (res.status === 401) {
      if (!retryingAfterRefresh && shouldRefreshForPath(path) && await refreshAccessToken()) {
        return apiWithMeta(method, path, body, true);
      }
      clearSession();
      window.location.replace('/login');
      return { data: null, totalCount: null };
    }

    const contentType = res.headers.get('Content-Type') || '';
    const isJson = contentType.includes('application/json');

    if (!res.ok) {
      let errMsg = `Error ${res.status}: ${res.statusText}`;
      if (isJson) {
        try {
          const errData = await res.json();
          errMsg = errData.detail || errData.message || errData.error || errMsg;
          if (Array.isArray(errData.detail)) {
            errMsg = errData.detail.map(e => e.msg || e.message || JSON.stringify(e)).join(', ');
          }
        } catch (_) {}
      }
      toast(errMsg, 'error');
      throw new Error(errMsg);
    }

    const totalHeader = res.headers.get('X-Total-Count');
    const parsedTotal = totalHeader === null ? null : Number(totalHeader);
    const totalCount = Number.isFinite(parsedTotal) ? parsedTotal : null;

    if (res.status === 204 || !isJson) return { data: null, totalCount };
    return { data: await res.json(), totalCount };
  } catch (err) {
    if (err.name === 'TypeError' && err.message.includes('fetch')) {
      toast('Sin conexión con el servidor', 'error');
    }
    throw err;
  }
}

function shouldRefreshForPath(path) {
  return !path.startsWith('/employees/login') &&
    !path.startsWith('/employees/refresh') &&
    !path.startsWith('/employees/logout');
}

async function refreshAccessToken() {
  const refreshToken = localStorage.getItem('wms_refresh');
  if (!refreshToken) return false;

  if (!refreshInFlight) {
    refreshInFlight = fetch('/api/v1/employees/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
      .then(async (res) => {
        if (!res.ok) return false;
        const data = await res.json().catch(() => ({}));
        if (!data.access_token) return false;
        localStorage.setItem('wms_token', data.access_token);
        return true;
      })
      .catch(() => false)
      .finally(() => { refreshInFlight = null; });
  }

  return refreshInFlight;
}

/* ============================================================
   Auth helpers
   ============================================================ */
function clearSession() {
  localStorage.removeItem('wms_token');
  localStorage.removeItem('wms_refresh');
  localStorage.removeItem('wms_user');
}

function logout() {
  const refreshToken = localStorage.getItem('wms_refresh');
  const finish = () => {
    clearSession();
    window.location.replace('/login');
  };

  if (!refreshToken) {
    finish();
    return;
  }

  fetch('/api/v1/employees/logout', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
    credentials: 'same-origin',
    body: JSON.stringify({ refresh_token: refreshToken }),
  }).finally(finish);
}

function getCurrentUser() {
  const raw = localStorage.getItem('wms_user');
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch (_) {
    clearSession();
    return null;
  }
}

function requireAuth() {
  if (!localStorage.getItem('wms_token')) {
    window.location.replace('/login');
    return false;
  }
  return true;
}

function currentUserInitials(user) {
  const name = (user?.full_name || `${user?.name || ''} ${user?.surname || ''}`).trim();
  if (!name) return 'U';
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map(part => part[0]?.toUpperCase() || '')
    .join('') || 'U';
}

function renderCurrentUser() {
  const user = getCurrentUser();
  const name = user?.full_name || `${user?.name || ''} ${user?.surname || ''}`.trim() || 'Usuario';
  const role = user?.role || '';
  const initials = currentUserInitials(user);

  document.querySelectorAll('[data-current-user-name]').forEach(el => { el.textContent = name; });
  document.querySelectorAll('[data-current-user-role]').forEach(el => { el.textContent = role; });
  document.querySelectorAll('[data-current-user-initials]').forEach(el => {
    el.textContent = initials;
    el.setAttribute('title', name);
  });
}

/* ============================================================
   Toast Notifications
   ============================================================ */
(function initToastContainer() {
  const init = () => {
    if (!document.getElementById('toast-container')) {
      const el = document.createElement('div');
      el.id = 'toast-container';
      document.body.appendChild(el);
    }
  };
  if (document.body) init();
  else document.addEventListener('DOMContentLoaded', init);
})();

function toast(message, type = 'info', duration = 4000) {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }

  const icons = {
    success: `<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>`,
    error:   `<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>`,
    warning: `<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>`,
    info:    `<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path stroke-linecap="round" stroke-linejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>`,
  };

  const t = document.createElement('div');
  t.className = `toast toast-${type}`;
  t.innerHTML = `
    ${icons[type] || icons.info}
    <span class="toast-msg">${message}</span>
    <button class="toast-close" aria-label="Cerrar">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
        <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
      </svg>
    </button>
  `;
  container.appendChild(t);

  const removeToast = () => {
    t.classList.add('removing');
    setTimeout(() => t.remove(), 260);
  };

  const timer = setTimeout(removeToast, duration);
  t.querySelector('.toast-close').addEventListener('click', () => {
    clearTimeout(timer);
    removeToast();
  });
}

/* ============================================================
   Date / Currency Formatters
   ============================================================ */
function formatDate(iso) {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleDateString('es-ES', { day: '2-digit', month: '2-digit', year: 'numeric' });
  } catch (_) { return iso; }
}

function formatDateTime(iso) {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleString('es-ES', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch (_) { return iso; }
}

function formatCurrency(amount) {
  if (amount === null || amount === undefined) return '—';
  return new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(amount);
}

function formatNumber(n, decimals = 0) {
  if (n === null || n === undefined) return '—';
  return new Intl.NumberFormat('es-ES', { minimumFractionDigits: decimals, maximumFractionDigits: decimals }).format(n);
}

/* ============================================================
   Barcode Scanner (USB HID keyboard emulation)
   ============================================================ */
const barcodeScanner = {
  _buffer: '',
  _timer: null,
  _callback: null,
  _lastKeyTime: 0,
  _minLength: 3,
  _timeout: 120,

  init(callback, minLength = 3) {
    this._callback = callback;
    this._minLength = minLength;
    this._handler = this._onKey.bind(this);
    document.addEventListener('keydown', this._handler);
  },

  destroy() {
    if (this._handler) document.removeEventListener('keydown', this._handler);
    this._buffer = '';
    clearTimeout(this._timer);
  },

  _onKey(e) {
    const tag = document.activeElement?.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;

    const now = Date.now();
    if (now - this._lastKeyTime > this._timeout && this._buffer.length > 0) {
      this._buffer = '';
    }
    this._lastKeyTime = now;

    if (e.key === 'Enter') {
      if (this._buffer.length >= this._minLength) {
        const code = this._buffer;
        this._buffer = '';
        clearTimeout(this._timer);
        if (this._callback) this._callback(code);
      }
      return;
    }

    if (e.key.length === 1) {
      this._buffer += e.key;
      clearTimeout(this._timer);
      this._timer = setTimeout(() => { this._buffer = ''; }, this._timeout * 5);
    }
  },

  fire(code) {
    if (code && code.length >= this._minLength && this._callback) {
      this._callback(code);
    }
  }
};

/* ============================================================
   Register Service Worker
   ============================================================ */
function registerSW() {
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/static/js/sw.js')
        .then(reg => {
          console.log('[SW] Registered:', reg.scope);
          reg.addEventListener('updatefound', () => {
            const newWorker = reg.installing;
            newWorker.addEventListener('statechange', () => {
              if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                toast('Nueva versión disponible. Recarga la página para actualizar.', 'info', 8000);
              }
            });
          });
        })
        .catch(err => console.warn('[SW] Registration failed:', err));
    });
  }
}

/* ============================================================
   Confirm Dialog (Promise-based)
   ============================================================ */
function confirmDialog(message, title = 'Confirmar acción') {
  return new Promise((resolve) => {
    const backdrop = document.createElement('div');
    backdrop.className = 'confirm-dialog';
    backdrop.innerHTML = `
      <div class="confirm-box">
        <div class="flex items-start gap-3 mb-4">
          <div class="flex-shrink-0 w-10 h-10 bg-amber-100 rounded-full flex items-center justify-center">
            <svg class="w-5 h-5 text-amber-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
            </svg>
          </div>
          <div>
            <h3 class="font-semibold text-gray-900">${title}</h3>
            <p class="text-sm text-gray-600 mt-1">${message}</p>
          </div>
        </div>
        <div class="flex gap-3 justify-end">
          <button id="confirm-cancel" class="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors">Cancelar</button>
          <button id="confirm-ok" class="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-lg transition-colors">Confirmar</button>
        </div>
      </div>
    `;
    document.body.appendChild(backdrop);

    const cleanup = (result) => { backdrop.remove(); resolve(result); };
    backdrop.querySelector('#confirm-ok').addEventListener('click', () => cleanup(true));
    backdrop.querySelector('#confirm-cancel').addEventListener('click', () => cleanup(false));
    backdrop.addEventListener('click', (e) => { if (e.target === backdrop) cleanup(false); });
  });
}

/* ============================================================
   Navigation Active Link Highlight
   ============================================================ */
function highlightActiveNav() {
  const path = window.location.pathname;
  document.querySelectorAll('.nav-link').forEach(link => {
    const href = link.getAttribute('href') || '';
    const isActive = href && (path === href || (href !== '/' && path.startsWith(href)));
    link.classList.toggle('active', isActive);
  });
}

/* ============================================================
   Utility helpers
   ============================================================ */
function debounce(fn, ms = 300) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function statusKey(status) {
  return String(status || '').toLowerCase();
}

function statusBadge(status) {
  const key = statusKey(status);
  const map = {
    pending: ['badge-pending', 'Pendiente'],
    picking: ['badge-picking', 'Picking'],
    completed: ['badge-completed', 'Completado'],
    cancelled: ['badge-cancelled', 'Cancelado'],
    returned: ['badge-returned', 'Devuelto'],
    confirmed: ['badge-confirmed', 'Confirmado'],
    draft: ['badge-draft', 'Borrador'],
    ok: ['badge-ok', 'OK'],
    low: ['badge-low', 'Bajo'],
    out: ['badge-out', 'Sin Stock'],
    high: ['badge-high', 'Alta'],
    medium: ['badge-medium', 'Media'],
    low_priority: ['badge-low-p', 'Baja'],
    active: ['badge-active', 'Activo'],
    inactive: ['badge-inactive', 'Inactivo'],
    maintenance: ['badge-maintenance', 'Mantenimiento'],
    scheduled: ['badge-picking', 'Programado'],
    in_route: ['badge-returned', 'En ruta'],
    in_transit: ['badge-returned', 'En Tránsito'],
    delivered: ['badge-completed', 'Entregado'],
    paid: ['badge-completed', 'Pagado'],
    generated: ['badge-picking', 'Generado'],
    partial: ['badge-returned', 'Parcial'],
    picked: ['badge-completed', 'Picado'],
    missing: ['badge-cancelled', 'Incidencia'],
  };
  const [cls, label] = map[key] || ['badge-draft', status || '?'];
  return `<span class="badge ${cls}">${label}</span>`;
}

function stockStatusBadge(current, minimum) {
  if (current <= 0) return statusBadge('out');
  if (current <= minimum) return statusBadge('low');
  return statusBadge('ok');
}

/* ============================================================
   Init on DOM ready
   ============================================================ */
document.addEventListener('DOMContentLoaded', () => {
  registerSW();
  highlightActiveNav();
  renderCurrentUser();
});
