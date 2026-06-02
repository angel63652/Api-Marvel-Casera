// Customer portal utilities. Keep this realm isolated from the internal WMS.
'use strict';

const PORTAL_TOKEN_KEY = 'portal_token';
const PORTAL_USER_KEY = 'portal_user';
const PORTAL_CUSTOMER_KEY = 'portal_customer';
const PORTAL_CART_KEY = 'portal_cart';

function portalApp() {
  return {
    ready: false,
    isAuthenticated: false,
    view: 'catalog',
    token: null,
    user: null,
    customer: null,
    profile: null,
    addresses: [],
    appError: '',

    authMode: 'login',
    authLoading: false,
    authError: '',
    loginForm: { email: '', password: '' },
    registerForm: {
      company_name: '',
      tax_id: '',
      email: '',
      password: '',
      name: '',
      phone: '',
    },

    catalog: [],
    catalogSearch: '',
    catalogLoading: false,
    catalogPage: 1,
    catalogPageSize: 12,
    catalogTotal: 0,
    searchTimer: null,
    stockStreamAbort: null,
    stockStreamRetry: null,

    cart: [],
    checkout: { shipping_address_id: '', notes: '' },
    orderSubmitting: false,
    orders: [],
    ordersLoading: false,

    changeRequests: [],
    changeSubmitting: false,
    changeForm: {
      target: 'FISCAL',
      fiscal: {
        company_name: '',
        tax_id: '',
        contact_email: '',
        contact_phone: '',
      },
      address: {
        label: '',
        line1: '',
        line2: '',
        city: '',
        province: '',
        postal_code: '',
        country: 'ES',
      },
    },

    get cartTotal() {
      return this.cart.reduce((sum, line) => {
        return sum + (Number(line.price || 0) * Number(line.quantity || 0));
      }, 0);
    },

    get catalogTotalPages() {
      return Math.max(1, Math.ceil((this.catalogTotal || 0) / this.catalogPageSize));
    },

    async init() {
      this.loadSession();
      this.loadCart();
      registerPortalSW();

      if (!this.token) {
        this.ready = true;
        return;
      }

      try {
        await this.fetchMe();
        await Promise.all([
          this.fetchCatalog(),
          this.fetchProfile(),
          this.fetchOrders(),
          this.fetchChangeRequests(),
        ]);
        this.startStockStream();
      } catch (_) {
        // portalApi already clears expired sessions.
      } finally {
        this.ready = true;
      }
    },

    loadSession() {
      this.token = localStorage.getItem(PORTAL_TOKEN_KEY);
      this.user = readJson(PORTAL_USER_KEY);
      this.customer = readJson(PORTAL_CUSTOMER_KEY);
      this.isAuthenticated = Boolean(this.token);
    },

    saveSession(data) {
      this.token = data.access_token;
      this.user = data.user || null;
      this.customer = data.customer || null;
      localStorage.setItem(PORTAL_TOKEN_KEY, this.token);
      localStorage.setItem(PORTAL_USER_KEY, JSON.stringify(this.user));
      localStorage.setItem(PORTAL_CUSTOMER_KEY, JSON.stringify(this.customer));
      this.isAuthenticated = true;
    },

    clearSession() {
      this.stopStockStream();
      this.token = null;
      this.user = null;
      this.customer = null;
      this.profile = null;
      this.addresses = [];
      this.orders = [];
      this.changeRequests = [];
      this.isAuthenticated = false;
      localStorage.removeItem(PORTAL_TOKEN_KEY);
      localStorage.removeItem(PORTAL_USER_KEY);
      localStorage.removeItem(PORTAL_CUSTOMER_KEY);
    },

    logout() {
      this.clearSession();
      this.view = 'catalog';
      this.authMode = 'login';
      this.authError = '';
      this.appError = '';
      portalToast('Sesion cerrada', 'info');
    },

    async login() {
      this.authLoading = true;
      this.authError = '';
      try {
        const { data } = await this.portalApi('POST', '/auth/login', this.loginForm, { auth: false });
        this.saveSession(data);
        await this.afterAuth();
      } catch (err) {
        this.authError = err.message || 'No se pudo iniciar sesion';
      } finally {
        this.authLoading = false;
      }
    },

    async register() {
      this.authLoading = true;
      this.authError = '';
      try {
        const { data } = await this.portalApi('POST', '/auth/register', this.registerForm, { auth: false });
        this.saveSession(data);
        portalToast('Registro creado. Cuenta pendiente de aprobacion.', 'success');
        await this.afterAuth();
      } catch (err) {
        this.authError = err.message || 'No se pudo registrar el cliente';
      } finally {
        this.authLoading = false;
      }
    },

    async afterAuth() {
      this.ready = true;
      await Promise.all([
        this.fetchCatalog(),
        this.fetchProfile(),
        this.fetchOrders(),
        this.fetchChangeRequests(),
      ]);
      this.startStockStream();
    },

    async portalApi(method, path, body = null, options = {}) {
      const needsAuth = options.auth !== false;
      const headers = { 'Content-Type': 'application/json', 'Accept': 'application/json' };
      if (needsAuth && this.token) headers.Authorization = `Bearer ${this.token}`;

      const request = {
        method: method.toUpperCase(),
        headers,
        credentials: 'same-origin',
      };
      if (body !== null) request.body = JSON.stringify(body);

      const res = await fetch(`/api/portal${path}`, request);

      if (res.status === 401 && needsAuth) {
        this.clearSession();
        this.authMode = 'login';
        throw new Error('Sesion caducada. Vuelve a iniciar sesion.');
      }

      const contentType = res.headers.get('Content-Type') || '';
      const isJson = contentType.includes('application/json');
      const data = isJson ? await res.json().catch(() => ({})) : null;

      if (!res.ok) {
        throw new Error(errorMessage(data, res));
      }

      const totalHeader = res.headers.get('X-Total-Count');
      const parsedTotal = totalHeader === null ? null : Number(totalHeader);
      return {
        data,
        totalCount: Number.isFinite(parsedTotal) ? parsedTotal : null,
      };
    },

    async fetchMe() {
      const { data } = await this.portalApi('GET', '/auth/me');
      this.saveSession(data);
      return data;
    },

    setView(nextView) {
      this.view = nextView;
      this.appError = '';
      if (nextView === 'catalog') this.fetchCatalog();
      if (nextView === 'orders') this.fetchOrders();
      if (nextView === 'profile') {
        this.fetchProfile();
        this.fetchChangeRequests();
      }
    },

    debouncedCatalogSearch() {
      clearTimeout(this.searchTimer);
      this.searchTimer = setTimeout(() => {
        this.catalogPage = 1;
        this.fetchCatalog();
      }, 250);
    },

    async fetchCatalog() {
      if (!this.isAuthenticated) return;
      this.catalogLoading = true;
      this.appError = '';
      try {
        const params = new URLSearchParams({
          limit: this.catalogPageSize,
          offset: (this.catalogPage - 1) * this.catalogPageSize,
        });
        if (this.catalogSearch) params.set('search', this.catalogSearch);
        const { data, totalCount } = await this.portalApi('GET', `/catalog?${params}`);
        this.catalog = (data || []).map(item => ({
          ...item,
          available_stock: Number(item.available_stock || 0),
          price: item.price === null || item.price === undefined ? null : Number(item.price),
          request_qty: 1,
        }));
        this.catalogTotal = totalCount ?? this.catalog.length;
      } catch (err) {
        this.appError = err.message;
      } finally {
        this.catalogLoading = false;
      }
    },

    changeCatalogPage(page) {
      this.catalogPage = Math.min(Math.max(1, page), this.catalogTotalPages);
      this.fetchCatalog();
    },

    startStockStream() {
      if (!this.token || this.stockStreamAbort || !window.ReadableStream) return;

      const controller = new AbortController();
      this.stockStreamAbort = controller;

      fetch('/api/portal/catalog/stream', {
        method: 'GET',
        headers: {
          'Accept': 'text/event-stream',
          'Authorization': `Bearer ${this.token}`,
        },
        credentials: 'same-origin',
        signal: controller.signal,
      })
        .then(async (res) => {
          if (res.status === 401) {
            this.clearSession();
            throw new Error('Sesion caducada. Vuelve a iniciar sesion.');
          }
          if (!res.ok || !res.body) {
            throw new Error(`Stream no disponible (${res.status})`);
          }
          await readSseStream(res.body.getReader(), (event) => this.applyStockEvent(event), controller.signal);
          if (!controller.signal.aborted) throw new Error('Stream cerrado');
        })
        .catch((err) => {
          if (controller.signal.aborted) return;
          console.warn('[Portal] Stock stream disconnected:', err);
          this.stockStreamAbort = null;
          clearTimeout(this.stockStreamRetry);
          this.stockStreamRetry = setTimeout(() => this.startStockStream(), 5000);
        });
    },

    stopStockStream() {
      clearTimeout(this.stockStreamRetry);
      this.stockStreamRetry = null;
      if (this.stockStreamAbort) {
        this.stockStreamAbort.abort();
        this.stockStreamAbort = null;
      }
    },

    applyStockEvent(event) {
      if (event.event !== 'stock') return;
      let payload;
      try {
        payload = JSON.parse(event.data);
      } catch (_) {
        return;
      }
      if (payload.type !== 'stock' || !payload.product_id) return;

      const available = Number(payload.available_stock || 0);
      const productId = Number(payload.product_id);
      const catalogItem = this.catalog.find(item => Number(item.id) === productId);
      if (catalogItem) catalogItem.available_stock = available;

      const cartLine = this.cart.find(line => Number(line.product_id) === productId);
      if (cartLine) {
        cartLine.available_stock = available;
        if (Number(cartLine.quantity || 0) > available) {
          cartLine.quantity = Math.max(0, available);
          portalToast(`Stock actualizado para ${cartLine.name}`, 'warning');
        }
        this.persistCart();
      }
    },

    loadCart() {
      const rows = readJson(PORTAL_CART_KEY);
      this.cart = Array.isArray(rows) ? rows : [];
    },

    persistCart() {
      this.cart = this.cart
        .map(line => ({
          ...line,
          quantity: clampQuantity(line.quantity, line.available_stock),
        }))
        .filter(line => line.quantity > 0);
      localStorage.setItem(PORTAL_CART_KEY, JSON.stringify(this.cart));
    },

    addToCart(item) {
      const requested = clampQuantity(item.request_qty, item.available_stock);
      if (requested <= 0) {
        portalToast('Producto sin stock disponible', 'warning');
        return;
      }

      const existing = this.cart.find(line => line.product_id === item.id);
      if (existing) {
        const nextQty = Number(existing.quantity || 0) + requested;
        if (nextQty > item.available_stock) {
          portalToast('No hay mas stock disponible para ese producto', 'warning');
          existing.quantity = item.available_stock;
        } else {
          existing.quantity = nextQty;
        }
      } else {
        this.cart.push({
          product_id: item.id,
          niu: item.niu,
          name: item.name,
          unit: item.unit,
          price: item.price,
          available_stock: item.available_stock,
          quantity: requested,
        });
      }

      this.persistCart();
      portalToast('Producto anadido al carrito', 'success');
    },

    removeFromCart(productId) {
      this.cart = this.cart.filter(line => line.product_id !== productId);
      this.persistCart();
    },

    clearCart() {
      this.cart = [];
      localStorage.removeItem(PORTAL_CART_KEY);
    },

    validateCart() {
      for (const line of this.cart) {
        if (Number(line.quantity || 0) <= 0) {
          return `Cantidad no valida para ${line.name}`;
        }
        if (Number(line.quantity || 0) > Number(line.available_stock || 0)) {
          return `Stock insuficiente para ${line.name}`;
        }
      }
      return '';
    },

    async submitOrder() {
      if (this.customer?.status !== 'ACTIVE') {
        portalToast('La cuenta debe estar aprobada para pedir', 'warning');
        return;
      }
      const cartError = this.validateCart();
      if (cartError) {
        portalToast(cartError, 'warning');
        return;
      }

      this.orderSubmitting = true;
      this.appError = '';
      try {
        const payload = {
          items: this.cart.map(line => ({
            product_id: line.product_id,
            quantity: Number(line.quantity),
          })),
          shipping_address_id: this.checkout.shipping_address_id || null,
          notes: this.checkout.notes || null,
        };
        const { data } = await this.portalApi('POST', '/orders', payload);
        this.clearCart();
        this.checkout = { shipping_address_id: '', notes: '' };
        await Promise.all([this.fetchOrders(), this.fetchCatalog()]);
        this.view = 'orders';
        portalToast(`Pedido ${data.order_number} creado`, 'success');
      } catch (err) {
        this.appError = err.message;
        portalToast(err.message, 'error');
      } finally {
        this.orderSubmitting = false;
      }
    },

    async fetchOrders() {
      if (!this.isAuthenticated) return;
      this.ordersLoading = true;
      try {
        const { data } = await this.portalApi('GET', '/orders');
        this.orders = data || [];
      } catch (err) {
        this.appError = err.message;
      } finally {
        this.ordersLoading = false;
      }
    },

    async fetchProfile() {
      if (!this.isAuthenticated) return;
      try {
        const { data } = await this.portalApi('GET', '/profile');
        this.profile = data;
        this.customer = data.customer || this.customer;
        this.addresses = data.addresses || [];
        localStorage.setItem(PORTAL_CUSTOMER_KEY, JSON.stringify(this.customer));
      } catch (err) {
        this.appError = err.message;
      }
    },

    async fetchChangeRequests() {
      if (!this.isAuthenticated) return;
      try {
        const { data } = await this.portalApi('GET', '/profile/change-requests');
        this.changeRequests = data || [];
      } catch (err) {
        this.appError = err.message;
      }
    },

    buildChangePayload() {
      const source = this.changeForm.target === 'FISCAL'
        ? this.changeForm.fiscal
        : this.changeForm.address;
      const payload = {};
      Object.entries(source).forEach(([key, value]) => {
        if (value !== null && value !== undefined && String(value).trim() !== '') {
          payload[key] = value;
        }
      });
      if (this.changeForm.target === 'ADDRESS' && !payload.country) payload.country = 'ES';
      return payload;
    },

    resetChangeForm() {
      this.changeForm.fiscal = {
        company_name: '',
        tax_id: '',
        contact_email: '',
        contact_phone: '',
      };
      this.changeForm.address = {
        label: '',
        line1: '',
        line2: '',
        city: '',
        province: '',
        postal_code: '',
        country: 'ES',
      };
    },

    async submitChangeRequest() {
      const payload = this.buildChangePayload();
      if (!Object.keys(payload).length) {
        portalToast('Completa al menos un campo para solicitar el cambio', 'warning');
        return;
      }

      this.changeSubmitting = true;
      try {
        await this.portalApi('POST', '/profile/change-request', {
          target: this.changeForm.target,
          payload,
        });
        this.resetChangeForm();
        await this.fetchChangeRequests();
        portalToast('Solicitud enviada a oficina', 'success');
      } catch (err) {
        portalToast(err.message, 'error');
      } finally {
        this.changeSubmitting = false;
      }
    },

    addressLabel(address) {
      return addressLabel(address);
    },
    customerStatusLabel(status) {
      return customerStatusLabel(status);
    },
    customerStatusClass(status) {
      return customerStatusClass(status);
    },
    orderStatusLabel(status) {
      return orderStatusLabel(status);
    },
    orderStatusClass(status) {
      return orderStatusClass(status);
    },
    requestStatusClass(status) {
      return requestStatusClass(status);
    },
    money(value) {
      return formatPortalCurrency(value);
    },
    number(value) {
      return formatPortalNumber(value);
    },
    dateTime(value) {
      return formatPortalDateTime(value);
    },
  };
}

async function readSseStream(reader, onEvent, signal) {
  const decoder = new TextDecoder();
  let buffer = '';

  while (!signal.aborted) {
    const { value, done } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split('\n\n');
    buffer = chunks.pop() || '';

    chunks.forEach((chunk) => {
      const parsed = parseSseChunk(chunk);
      if (parsed.data) onEvent(parsed);
    });
  }
}

function parseSseChunk(chunk) {
  const parsed = { event: 'message', data: '' };
  const dataLines = [];

  chunk.split(/\r?\n/).forEach((line) => {
    if (!line || line.startsWith(':')) return;
    if (line.startsWith('event:')) parsed.event = line.slice(6).trim();
    if (line.startsWith('data:')) dataLines.push(line.slice(5).trim());
  });

  parsed.data = dataLines.join('\n');
  return parsed;
}

function readJson(key) {
  const raw = localStorage.getItem(key);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch (_) {
    localStorage.removeItem(key);
    return null;
  }
}

function errorMessage(data, res) {
  if (Array.isArray(data?.detail)) {
    return data.detail.map(item => item.msg || item.message || JSON.stringify(item)).join(', ');
  }
  return data?.detail || data?.message || data?.error || `Error ${res.status}: ${res.statusText}`;
}

function clampQuantity(value, available) {
  const qty = Number(value || 0);
  const max = Number(available || 0);
  if (!Number.isFinite(qty) || qty <= 0) return 0;
  if (max <= 0) return 0;
  return Math.min(qty, max);
}

function formatPortalCurrency(value) {
  if (value === null || value === undefined || value === '') return 'Sin precio';
  return new Intl.NumberFormat('es-ES', { style: 'currency', currency: 'EUR' }).format(Number(value));
}

function formatPortalNumber(value) {
  if (value === null || value === undefined) return '0';
  return new Intl.NumberFormat('es-ES', { maximumFractionDigits: 2 }).format(Number(value));
}

function formatPortalDateTime(value) {
  if (!value) return '-';
  try {
    return new Date(value).toLocaleString('es-ES', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch (_) {
    return value;
  }
}

function customerStatusLabel(status) {
  const map = { ACTIVE: 'Activa', PENDING: 'Pendiente', SUSPENDED: 'Suspendida' };
  return map[status] || status || 'Sin estado';
}

function customerStatusClass(status) {
  const map = {
    ACTIVE: 'bg-emerald-100 text-emerald-700',
    PENDING: 'bg-amber-100 text-amber-700',
    SUSPENDED: 'bg-red-100 text-red-700',
  };
  return map[status] || 'bg-slate-100 text-slate-600';
}

function orderStatusLabel(status) {
  const map = {
    PENDING: 'Pendiente',
    PICKING: 'En preparacion',
    COMPLETED: 'Completado',
    CANCELLED: 'Cancelado',
    RETURNED: 'Devuelto',
  };
  return map[status] || status || 'Sin estado';
}

function orderStatusClass(status) {
  const map = {
    PENDING: 'bg-amber-100 text-amber-700',
    PICKING: 'bg-blue-100 text-blue-700',
    COMPLETED: 'bg-emerald-100 text-emerald-700',
    CANCELLED: 'bg-red-100 text-red-700',
    RETURNED: 'bg-purple-100 text-purple-700',
  };
  return map[status] || 'bg-slate-100 text-slate-600';
}

function requestStatusClass(status) {
  const map = {
    PENDING: 'bg-amber-100 text-amber-700',
    APPROVED: 'bg-emerald-100 text-emerald-700',
    REJECTED: 'bg-red-100 text-red-700',
  };
  return map[status] || 'bg-slate-100 text-slate-600';
}

function addressLabel(address) {
  const label = address.label || address.type || 'Direccion';
  const city = address.city ? ` - ${address.city}` : '';
  return `${label}${city}`;
}

function portalToast(message, type = 'info', duration = 4000) {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <span class="toast-msg">${escapePortalHtml(message)}</span>
    <button class="toast-close" aria-label="Cerrar">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
        <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
      </svg>
    </button>
  `;
  container.appendChild(toast);

  const remove = () => {
    toast.classList.add('removing');
    setTimeout(() => toast.remove(), 260);
  };
  const timer = setTimeout(remove, duration);
  toast.querySelector('.toast-close').addEventListener('click', () => {
    clearTimeout(timer);
    remove();
  });
}

function escapePortalHtml(value) {
  return String(value || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function registerPortalSW() {
  if (!('serviceWorker' in navigator)) return;
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/portal-sw.js', { scope: '/portal' })
      .catch(err => console.warn('[Portal SW] Registration failed:', err));
  });
}
