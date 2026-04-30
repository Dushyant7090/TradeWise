/**
 * http-client.js - Shared fetch client with dedupe, cache, and SWR.
 */

export class HttpClientError extends Error {
  constructor(message, status = 0, data = null) {
    super(message || 'Request failed');
    this.name = 'HttpClientError';
    this.status = status;
    this.data = data;
  }
}

const DEFAULT_CACHE_POLICY = {
  ttlMs: 0,
  staleMs: 0,
  swr: false,
  persist: null,
};

function normalizeCachePolicy(policy = {}) {
  return {
    ttlMs: Number(policy.ttlMs || 0),
    staleMs: Number(policy.staleMs || 0),
    swr: Boolean(policy.swr),
    persist: policy.persist === 'local' || policy.persist === 'session' ? policy.persist : null,
  };
}

function readPersistentEntry(store, key) {
  if (!store) return null;
  try {
    const raw = store.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object') return null;
    return parsed;
  } catch {
    return null;
  }
}

function writePersistentEntry(store, key, value) {
  if (!store) return;
  try {
    store.setItem(key, JSON.stringify(value));
  } catch {
    // Ignore storage quota/privacy mode errors.
  }
}

function removePersistentEntry(store, key) {
  if (!store) return;
  try {
    store.removeItem(key);
  } catch {
    // Ignore storage errors.
  }
}

export function createHttpClient(config = {}) {
  const FALLBACK_LOCAL_API_BASE = 'http://localhost:5000/api';
  const rawBaseUrl = (config.baseUrl || '').replace(/\/$/, '');
  const baseUrl = /^https?:\/\/10\.25\.183\.119:5000\/api$/i.test(rawBaseUrl)
    ? FALLBACK_LOCAL_API_BASE
    : rawBaseUrl;
  const storagePrefix = config.storagePrefix || 'tw_api_cache';
  const getToken = typeof config.getToken === 'function' ? config.getToken : (() => null);
  const refreshAuth = typeof config.refreshAuth === 'function' ? config.refreshAuth : null;
  const onAuthFailure = typeof config.onAuthFailure === 'function' ? config.onAuthFailure : null;
  const defaultPolicy = normalizeCachePolicy(config.defaultCachePolicy || DEFAULT_CACHE_POLICY);

  const memoryCache = new Map();
  const inflight = new Map();

  const localStore = typeof window !== 'undefined' ? window.localStorage : null;
  const sessionStore = typeof window !== 'undefined' ? window.sessionStorage : null;

  function fullUrl(endpoint) {
    if (!endpoint) return baseUrl;
    if (/^https?:\/\//i.test(endpoint)) return endpoint;
    const normalized = endpoint.startsWith('/') ? endpoint : `/${endpoint}`;
    return `${baseUrl}${normalized}`;
  }

  function cacheStorageKey(cacheKey) {
    return `${storagePrefix}:${cacheKey}`;
  }

  function buildCacheKey(method, endpoint, customKey = '') {
    if (customKey) return String(customKey);
    return `${method.toUpperCase()}:${endpoint}`;
  }

  function getStore(mode) {
    if (mode === 'local') return localStore;
    if (mode === 'session') return sessionStore;
    return null;
  }

  function getCached(cacheKey, policy) {
    const now = Date.now();
    const inMemory = memoryCache.get(cacheKey);
    if (inMemory) {
      if (inMemory.expiresAt > now) {
        return { hit: true, stale: false, value: inMemory.value };
      }
      if (inMemory.staleUntil > now) {
        return { hit: true, stale: true, value: inMemory.value };
      }
      memoryCache.delete(cacheKey);
    }

    if (!policy.persist) return null;

    const persistentKey = cacheStorageKey(cacheKey);
    const store = getStore(policy.persist);
    const persisted = readPersistentEntry(store, persistentKey);
    if (!persisted) return null;

    if (persisted.expiresAt > now) {
      memoryCache.set(cacheKey, persisted);
      return { hit: true, stale: false, value: persisted.value };
    }

    if (persisted.staleUntil > now) {
      memoryCache.set(cacheKey, persisted);
      return { hit: true, stale: true, value: persisted.value };
    }

    removePersistentEntry(store, persistentKey);
    return null;
  }

  function setCached(cacheKey, value, policy) {
    if (policy.ttlMs <= 0 && policy.staleMs <= 0) return;

    const now = Date.now();
    const entry = {
      value,
      expiresAt: now + Math.max(0, policy.ttlMs),
      staleUntil: now + Math.max(0, policy.ttlMs + policy.staleMs),
    };

    memoryCache.set(cacheKey, entry);

    if (policy.persist) {
      const store = getStore(policy.persist);
      writePersistentEntry(store, cacheStorageKey(cacheKey), entry);
    }
  }

  function clearCached(cacheKey) {
    memoryCache.delete(cacheKey);
    removePersistentEntry(localStore, cacheStorageKey(cacheKey));
    removePersistentEntry(sessionStore, cacheStorageKey(cacheKey));
  }

  function invalidate(predicate) {
    const matcher = typeof predicate === 'function'
      ? predicate
      : (cacheKey) => String(cacheKey).includes(String(predicate || ''));

    [...memoryCache.keys()].forEach((key) => {
      if (matcher(key)) {
        clearCached(key);
      }
    });

    const clearStoreByPredicate = (store) => {
      if (!store) return;
      try {
        const toRemove = [];
        for (let i = 0; i < store.length; i += 1) {
          const key = store.key(i);
          if (!key || !key.startsWith(`${storagePrefix}:`)) continue;
          const plain = key.slice(storagePrefix.length + 1);
          if (matcher(plain)) toRemove.push(key);
        }
        toRemove.forEach((key) => store.removeItem(key));
      } catch {
        // Ignore storage errors.
      }
    };

    clearStoreByPredicate(localStore);
    clearStoreByPredicate(sessionStore);
  }

  function invalidateByEndpoint(endpoint) {
    const normalized = String(endpoint || '');
    if (!normalized) {
      invalidate(() => true);
      return;
    }

    const root = normalized.split('?')[0].split('/').slice(0, 3).join('/');
    invalidate((cacheKey) => cacheKey.includes(root));
  }

  async function parseJsonSafe(response) {
    try {
      return await response.json();
    } catch {
      return {};
    }
  }

  async function fetchWithAuthRetry(url, options, canRetry) {
    const response = await fetch(url, options);
    if (response.status !== 401 || !canRetry || !refreshAuth) {
      return response;
    }

    const refreshed = await refreshAuth();
    if (!refreshed) {
      if (onAuthFailure) onAuthFailure();
      return response;
    }

    const newToken = getToken();
    const retryHeaders = {
      ...(options.headers || {}),
      ...(newToken ? { Authorization: `Bearer ${newToken}` } : {}),
    };

    return fetch(url, {
      ...options,
      headers: retryHeaders,
    });
  }

  async function request(endpoint, opts = {}) {
    const method = String(opts.method || 'GET').toUpperCase();
    const url = fullUrl(endpoint);
    const isGet = method === 'GET';
    const dedupe = opts.dedupe !== false;
    const cachePolicy = normalizeCachePolicy(opts.cachePolicy || defaultPolicy);
    const cacheKey = buildCacheKey(method, endpoint, opts.cacheKey);

    if (isGet && !opts.forceRefresh && (cachePolicy.ttlMs > 0 || cachePolicy.staleMs > 0)) {
      const cached = getCached(cacheKey, cachePolicy);
      if (cached && !cached.stale) {
        return cached.value;
      }
      if (cached && cached.stale && cachePolicy.swr) {
        // Serve stale immediately and refresh in background.
        void request(endpoint, { ...opts, forceRefresh: true }).catch(() => null);
        return cached.value;
      }
    }

    if (isGet && dedupe && inflight.has(cacheKey)) {
      return inflight.get(cacheKey);
    }

    const token = getToken();
    const headers = {
      ...(opts.headers || {}),
      ...(token && !opts.skipAuth ? { Authorization: `Bearer ${token}` } : {}),
    };

    const fetchOptions = {
      method,
      headers,
      body: opts.body,
    };

    const fetchPromise = (async () => {
      const response = await fetchWithAuthRetry(url, fetchOptions, !opts.skipAuthRetry);
      const payload = await parseJsonSafe(response);

      if (!response.ok) {
        const message = payload.message || payload.error || response.statusText || 'Request failed';
        throw new HttpClientError(message, response.status, payload);
      }

      if (isGet && (cachePolicy.ttlMs > 0 || cachePolicy.staleMs > 0)) {
        setCached(cacheKey, payload, cachePolicy);
      }

      if (!isGet) {
        if (Array.isArray(opts.invalidateKeys) && opts.invalidateKeys.length > 0) {
          opts.invalidateKeys.forEach((key) => invalidate(key));
        } else {
          invalidateByEndpoint(endpoint);
        }
      }

      return payload;
    })();

    if (isGet && dedupe) {
      inflight.set(cacheKey, fetchPromise);
      fetchPromise.finally(() => inflight.delete(cacheKey));
    }

    return fetchPromise;
  }

  async function prefetch(endpoint, opts = {}) {
    try {
      await request(endpoint, { ...opts, method: 'GET' });
      return true;
    } catch {
      return false;
    }
  }

  return {
    request,
    get: (endpoint, opts = {}) => request(endpoint, { ...opts, method: 'GET' }),
    post: (endpoint, opts = {}) => request(endpoint, { ...opts, method: 'POST' }),
    put: (endpoint, opts = {}) => request(endpoint, { ...opts, method: 'PUT' }),
    patch: (endpoint, opts = {}) => request(endpoint, { ...opts, method: 'PATCH' }),
    delete: (endpoint, opts = {}) => request(endpoint, { ...opts, method: 'DELETE' }),
    prefetch,
    invalidate,
    clearCached,
  };
}
