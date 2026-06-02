/* ============================================================
   WMS Almacén - Dedicated Picking Interface JavaScript
   ============================================================ */

'use strict';

/* ============================================================
   BarcodeScanner Class
   Handles USB scanner (rapid keypress emulation) AND manual input
   ============================================================ */
class BarcodeScanner {
  constructor(options = {}) {
    this.onScan = options.onScan || null;
    this.minLength = options.minLength || 3;
    this.timeout = options.timeout || 100; // ms between chars for USB scanner
    this._buffer = '';
    this._lastTime = 0;
    this._timer = null;
    this._bound = this._onKey.bind(this);
  }

  start() {
    document.addEventListener('keydown', this._bound);
  }

  stop() {
    document.removeEventListener('keydown', this._bound);
    clearTimeout(this._timer);
    this._buffer = '';
  }

  _onKey(e) {
    // Only capture when no input/textarea is focused (global scanner capture)
    const active = document.activeElement;
    if (active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA')) return;

    const now = Date.now();
    if (now - this._lastTime > this.timeout * 3 && this._buffer) {
      this._buffer = '';
    }
    this._lastTime = now;

    if (e.key === 'Enter') {
      e.preventDefault();
      this._flush();
      return;
    }

    if (e.key.length === 1) {
      this._buffer += e.key;
      clearTimeout(this._timer);
      this._timer = setTimeout(() => this._flush(), this.timeout * 5);
    }
  }

  _flush() {
    const code = this._buffer.trim();
    this._buffer = '';
    if (code.length >= this.minLength && this.onScan) {
      this.onScan(code);
    }
  }

  // Manually fire with a barcode value (from text input)
  fire(code) {
    if (code && code.trim().length >= this.minLength && this.onScan) {
      this.onScan(code.trim());
    }
  }
}

/* ============================================================
   IndexedDB-backed offline queue
   ============================================================ */
class PickingOfflineQueue {
  constructor() {
    this.dbName = 'wms-picking-offline';
    this.storeName = 'actions';
    this.legacyKey = 'wms_picking_queue';
    this.db = null;
    this.useFallback = !('indexedDB' in window);
  }

  async init() {
    if (this.useFallback) return;
    try {
      this.db = await this._openDb();
      await this._migrateLegacyQueue();
    } catch (_) {
      this.db = null;
      this.useFallback = true;
    }
  }

  async list() {
    if (this.useFallback) return this._fallbackList();
    const tx = this.db.transaction(this.storeName, 'readonly');
    const store = tx.objectStore(this.storeName);
    const items = await this._request(store.getAll());
    return items.sort((a, b) => (a.timestamp || 0) - (b.timestamp || 0));
  }

  async enqueue(action) {
    const record = {
      ...action,
      timestamp: action.timestamp || Date.now(),
    };
    if (this.useFallback) return this._fallbackEnqueue(record);

    const tx = this.db.transaction(this.storeName, 'readwrite');
    const store = tx.objectStore(this.storeName);
    const id = await this._request(store.add(record));
    return { ...record, id };
  }

  async remove(id) {
    if (this.useFallback) return this._fallbackRemove(id);
    const tx = this.db.transaction(this.storeName, 'readwrite');
    const store = tx.objectStore(this.storeName);
    await this._request(store.delete(id));
  }

  _openDb() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(this.dbName, 1);
      request.onupgradeneeded = () => {
        const db = request.result;
        if (!db.objectStoreNames.contains(this.storeName)) {
          const store = db.createObjectStore(this.storeName, {
            keyPath: 'id',
            autoIncrement: true,
          });
          store.createIndex('by_timestamp', 'timestamp');
          store.createIndex('by_order', 'orderId');
        }
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  _request(request) {
    return new Promise((resolve, reject) => {
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  async _migrateLegacyQueue() {
    const legacy = this._fallbackList();
    if (!legacy.length) return;
    for (const action of legacy) {
      await this.enqueue(action);
    }
    localStorage.removeItem(this.legacyKey);
  }

  _fallbackList() {
    try {
      return JSON.parse(localStorage.getItem(this.legacyKey) || '[]');
    } catch (_) {
      return [];
    }
  }

  _fallbackEnqueue(action) {
    const record = {
      ...action,
      id: action.id || `${Date.now()}-${Math.random().toString(36).slice(2)}`,
    };
    const items = this._fallbackList();
    items.push(record);
    localStorage.setItem(this.legacyKey, JSON.stringify(items));
    return record;
  }

  _fallbackRemove(id) {
    const items = this._fallbackList().filter(action => action.id !== id);
    localStorage.setItem(this.legacyKey, JSON.stringify(items));
  }
}

/* ============================================================
   PickingManager Class
   ============================================================ */
class PickingManager {
  constructor() {
    this.orderId = null;
    this.orderData = null;
    this.lines = [];
    this.currentLineIndex = 0;
    this.offlineQueue = [];
    this.queueStore = new PickingOfflineQueue();
    this.offlineReady = this._loadOfflineQueue();

    this.scanner = new BarcodeScanner({
      onScan: (code) => this.matchBarcode(code),
      minLength: 3,
      timeout: 100,
    });

    // Audio context for beep
    this._audioCtx = null;
  }

  /* ---- Load order ---- */
  async loadOrder(orderId) {
    this.orderId = orderId;
    await this.offlineReady;
    try {
      const lines = await api('GET', `/orders/${orderId}/picking-list`);
      const order = await api('GET', `/orders/${orderId}`);
      this.orderData = order;
      this.lines = (Array.isArray(lines) ? lines : lines.lines || []).map(line => this._normalizeLine(line));
      this.currentLineIndex = this._findFirstPending();
      this.scanner.start();
      return order;
    } catch (err) {
      toast('Error al cargar la orden de picking', 'error');
      throw err;
    }
  }

  /* ---- Match barcode to a line ---- */
  matchBarcode(barcode) {
    const match = this.lines.find(l =>
      (l.product_barcode === barcode || l.product_niu === barcode) &&
      statusKey(l.status) === 'pending'
    );

    if (match) {
      this.feedbackSuccess();
      const idx = this.lines.indexOf(match);
      this.currentLineIndex = idx;
      this._renderCurrentLine();
      toast(`Producto encontrado: ${match.product_name}`, 'success', 2000);
      return match;
    } else {
      this.feedbackError();
      toast(`Código no encontrado: ${barcode}`, 'warning', 3000);
      return null;
    }
  }

  /* ---- Pick a line ---- */
  async pickLine(lineId, qty, notes = '') {
    const payload = { quantity_picked: qty, observation: notes || null };

    if (!navigator.onLine) {
      await this._queueOffline({ type: 'pick', orderId: this.orderId, lineId, payload });
      this._markLineLocally(lineId, 'picked', qty);
      toast('Sin conexión — guardado localmente', 'warning');
      return;
    }

    try {
      const result = await api('POST', `/orders/${this.orderId}/lines/${lineId}/pick`, payload);
      this._markLineLocally(lineId, 'picked', qty);
      this.feedbackSuccess();
      return result;
    } catch (err) {
      await this._queueOffline({ type: 'pick', orderId: this.orderId, lineId, payload });
      throw err;
    }
  }

  /* ---- Add observation ---- */
  async addObservation(lineId, type, notes) {
    const payload = { observation: notes, status: 'MISSING' };

    if (!navigator.onLine) {
      await this._queueOffline({ type: 'observation', orderId: this.orderId, lineId, payload });
      this._markLineLocally(lineId, 'observed', 0);
      toast('Sin conexión — observación guardada localmente', 'warning');
      return;
    }

    try {
      const result = await api('POST', `/orders/${this.orderId}/lines/${lineId}/observe`, payload);
      this._markLineLocally(lineId, 'observed', 0);
      return result;
    } catch (err) {
      await this._queueOffline({ type: 'observation', orderId: this.orderId, lineId, payload });
      throw err;
    }
  }

  /* ---- Navigate to next pending line ---- */
  navigateToNextPending() {
    const nextIdx = this.lines.findIndex((l, i) => i > this.currentLineIndex && statusKey(l.status) === 'pending');
    if (nextIdx !== -1) {
      this.currentLineIndex = nextIdx;
    } else {
      // wrap around
      const fromStart = this.lines.findIndex(l => statusKey(l.status) === 'pending');
      if (fromStart !== -1) {
        this.currentLineIndex = fromStart;
      } else {
        return false; // all done
      }
    }
    this._renderCurrentLine();
    return true;
  }

  /* ---- Check if all lines processed ---- */
  allProcessed() {
    return this.lines.every(l => statusKey(l.status) !== 'pending');
  }

  pickedCount() {
    return this.lines.filter(l => statusKey(l.status) === 'picked').length;
  }

  totalCount() {
    return this.lines.length;
  }

  progressPct() {
    if (!this.lines.length) return 0;
    return Math.round((this.lines.filter(l => statusKey(l.status) !== 'pending').length / this.lines.length) * 100);
  }

  /* ---- Complete order (show conformity screen) ---- */
  completeOrder() {
    document.dispatchEvent(new CustomEvent('picking:showConformity'));
  }

  /* ---- Confirm conformity ---- */
  async confirmConformity(notes) {
    try {
      const result = await api('POST', `/orders/${this.orderId}/confirm`, { conformity_notes: notes || null });
      this.scanner.stop();
      await this._syncOfflineQueue();
      return result;
    } catch (err) {
      toast('Error al confirmar conformidad', 'error');
      throw err;
    }
  }

  /* ---- Offline queue ---- */
  async _loadOfflineQueue() {
    try {
      await this.queueStore.init();
      this.offlineQueue = await this.queueStore.list();
    } catch (_) { this.offlineQueue = []; }
    this._emitQueueUpdated();
  }

  async _queueOffline(action) {
    await this.offlineReady;
    await this.queueStore.enqueue(action);
    this.offlineQueue = await this.queueStore.list();
    this._emitQueueUpdated();
    this._registerBackgroundSync();
  }

  async _syncOfflineQueue() {
    await this.offlineReady;
    this.offlineQueue = await this.queueStore.list();
    this._emitQueueUpdated();
    if (!this.offlineQueue.length) return;

    const pending = [...this.offlineQueue];

    let synced = 0, failed = 0;
    for (const action of pending) {
      try {
        if (action.type === 'pick') {
          await api('POST', `/orders/${action.orderId}/lines/${action.lineId}/pick`, action.payload);
        } else if (action.type === 'observation') {
          await api('POST', `/orders/${action.orderId}/lines/${action.lineId}/observe`, action.payload);
        }
        await this.queueStore.remove(action.id);
        synced++;
      } catch (_) {
        failed++;
      }
    }
    this.offlineQueue = await this.queueStore.list();
    this._emitQueueUpdated();

    if (synced > 0) toast(`${synced} acción(es) sincronizadas`, 'success');
    if (failed > 0) toast(`${failed} acción(es) no pudieron sincronizarse`, 'error');
  }

  _emitQueueUpdated() {
    document.dispatchEvent(new CustomEvent('picking:queueUpdated', {
      detail: { count: this.offlineQueue.length },
    }));
  }

  _registerBackgroundSync() {
    if (!('serviceWorker' in navigator) || !('SyncManager' in window)) return;
    navigator.serviceWorker.ready
      .then(registration => registration.sync.register('sync-picking-queue'))
      .catch(() => {});
  }

  /* ---- Local state mutation ---- */
  _markLineLocally(lineId, status, qty) {
    const line = this.lines.find(l => l.id === lineId);
    if (line) {
      line.status = status;
      if (qty !== undefined) line.quantity_picked = qty;
    }
    document.dispatchEvent(new CustomEvent('picking:lineUpdated', { detail: { lineId, status } }));
  }

  _findFirstPending() {
    const idx = this.lines.findIndex(l => statusKey(l.status) === 'pending');
    return idx === -1 ? 0 : idx;
  }

  _normalizeLine(line) {
    return {
      ...line,
      id: line.id ?? line.line_id,
      quantity_needed: line.quantity_needed ?? line.quantity_requested ?? 0,
      status: statusKey(line.status || 'PENDING'),
    };
  }

  _renderCurrentLine() {
    document.dispatchEvent(new CustomEvent('picking:renderLine', { detail: { index: this.currentLineIndex } }));
  }

  currentLine() {
    return this.lines[this.currentLineIndex] || null;
  }

  /* ---- Feedback ---- */
  feedbackSuccess() {
    this._beep(880, 0.15, 0.1);
    if ('vibrate' in navigator) navigator.vibrate([50]);
  }

  feedbackError() {
    this._beep(220, 0.3, 0.15);
    if ('vibrate' in navigator) navigator.vibrate([100, 50, 100]);
  }

  _beep(freq = 880, vol = 0.2, dur = 0.1) {
    try {
      if (!this._audioCtx) this._audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = this._audioCtx.createOscillator();
      const gain = this._audioCtx.createGain();
      osc.connect(gain);
      gain.connect(this._audioCtx.destination);
      osc.frequency.value = freq;
      gain.gain.setValueAtTime(vol, this._audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, this._audioCtx.currentTime + dur);
      osc.start(this._audioCtx.currentTime);
      osc.stop(this._audioCtx.currentTime + dur);
    } catch (_) {}
  }
}

/* ============================================================
   Picking Page Controller (Alpine.js data)
   ============================================================ */
function pickingPageData() {
  return {
    orderId: null,
    order: null,
    lines: [],
    currentLine: null,
    currentIndex: 0,
    qtyPicked: 1,
    barcodeInput: '',
    showConformity: false,
    conformityNotes: '',
    showObsModal: false,
    obsType: '',
    obsNotes: '',
    obsLineId: null,
    showSummary: false,
    showCelebration: false,
    loading: true,
    submitting: false,
    offlineQueueCountValue: 0,
    manager: null,

    async init() {
      const params = new URLSearchParams(window.location.search);
      this.orderId = params.get('order_id') || params.get('id');
      if (!this.orderId) {
        toast('No se especificó una orden', 'error');
        this.loading = false;
        return;
      }

      this.manager = new PickingManager();

      // Listen for events from manager
      document.addEventListener('picking:renderLine', (e) => {
        this.currentIndex = e.detail.index;
        this.currentLine = this.manager.currentLine();
        this.qtyPicked = this.currentLine?.quantity_needed || 1;
        this.lines = [...this.manager.lines];
      });

      document.addEventListener('picking:lineUpdated', () => {
        this.lines = [...this.manager.lines];
      });

      document.addEventListener('picking:showConformity', () => {
        this.showConformity = true;
      });

      document.addEventListener('picking:queueUpdated', (e) => {
        this.offlineQueueCountValue = e.detail.count || 0;
      });

      // Sync offline queue when back online
      window.addEventListener('online', () => {
        toast('Conexión restaurada — sincronizando...', 'info');
        this.manager._syncOfflineQueue();
      });

      navigator.serviceWorker?.addEventListener('message', (event) => {
        if (event.data?.type === 'SYNC_PICKING_QUEUE') {
          this.manager._syncOfflineQueue();
        }
      });

      try {
        const data = await this.manager.loadOrder(this.orderId);
        this.order = data;
        this.lines = [...this.manager.lines];
        this.currentLine = this.manager.currentLine();
        this.qtyPicked = this.currentLine?.quantity_needed || 1;
        this.offlineQueueCountValue = this.manager.offlineQueue.length;
      } catch (_) {
        toast('No se pudo cargar la orden', 'error');
      } finally {
        this.loading = false;
      }
    },

    onBarcodeInput(e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        this.handleBarcodeScan();
      }
    },

    handleBarcodeScan() {
      const code = this.barcodeInput.trim();
      if (!code) return;
      const found = this.manager.matchBarcode(code);
      if (found) {
        this.currentLine = this.manager.currentLine();
        this.qtyPicked = this.currentLine?.quantity_needed || 1;
      }
      this.barcodeInput = '';
    },

    async doPick() {
      if (!this.currentLine || this.submitting) return;
      this.submitting = true;
      try {
        await this.manager.pickLine(this.currentLine.id, this.qtyPicked);
        this.lines = [...this.manager.lines];
        if (this.manager.allProcessed()) {
          this.manager.completeOrder();
        } else {
          this.manager.navigateToNextPending();
          this.currentLine = this.manager.currentLine();
          this.qtyPicked = this.currentLine?.quantity_needed || 1;
        }
      } finally {
        this.submitting = false;
      }
    },

    openObsModal(type) {
      this.obsType = type;
      this.obsNotes = '';
      this.obsLineId = this.currentLine?.id;
      this.showObsModal = true;
    },

    async submitObservation() {
      if (!this.obsLineId || this.submitting) return;
      this.submitting = true;
      try {
        await this.manager.addObservation(this.obsLineId, this.obsType, this.obsNotes);
        this.showObsModal = false;
        this.lines = [...this.manager.lines];
        if (this.manager.allProcessed()) {
          this.manager.completeOrder();
        } else {
          this.manager.navigateToNextPending();
          this.currentLine = this.manager.currentLine();
          this.qtyPicked = this.currentLine?.quantity_needed || 1;
        }
      } finally {
        this.submitting = false;
      }
    },

    skipLine() {
      const hasNext = this.manager.navigateToNextPending();
      if (hasNext) {
        this.currentLine = this.manager.currentLine();
        this.qtyPicked = this.currentLine?.quantity_needed || 1;
      }
    },

    async doConfirmConformity() {
      if (this.submitting) return;
      this.submitting = true;
      try {
        await this.manager.confirmConformity(this.conformityNotes);
        this.showConformity = false;
        this.showCelebration = true;
        setTimeout(() => {
          window.location.href = '/orders';
        }, 3000);
      } finally {
        this.submitting = false;
      }
    },

    get progress() { return this.manager ? this.manager.progressPct() : 0; },
    get pickedCount() { return this.manager ? this.manager.pickedCount() : 0; },
    get totalCount() { return this.manager ? this.manager.totalCount() : 0; },
    get allDone() { return this.manager ? this.manager.allProcessed() : false; },
    get offlineQueueCount() { return this.offlineQueueCountValue; },

    lineStatusIcon(status) {
      if (status === 'picked') return '✓';
      if (status === 'observed') return '⚠';
      return '○';
    },
    lineStatusClass(status) {
      if (status === 'picked') return 'text-green-600 font-bold';
      if (status === 'observed') return 'text-amber-600 font-bold';
      return 'text-gray-400';
    },

    formatLocation(line) {
      if (!line) return '';
      const parts = [];
      if (line.aisle) parts.push(line.aisle);
      if (line.rack) parts.push(line.rack);
      if (line.position) parts.push(line.position);
      return parts.join(' → ');
    },
  };
}

// Expose globally
window.PickingManager = PickingManager;
window.BarcodeScanner = BarcodeScanner;
window.PickingOfflineQueue = PickingOfflineQueue;
window.pickingPageData = pickingPageData;
