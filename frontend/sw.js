/*
 * MedSure Vision — Service Worker (Offline-First PWA)
 *
 * Strategy:
 *   - App shell (HTML, icons, manifest) → Cache-First
 *   - API requests to /scan, /demo, /alerts, etc → Network-First with cache fallback
 *   - Stale-while-revalidate for non-critical assets
 *
 * The service worker enables full offline operation after the first visit,
 * which is essential for rural pharmacies and warehouses with unreliable connectivity.
 */

const CACHE_NAME = 'medsure-v1';
const APP_SHELL = [
  '/',
  '/index.html',
  '/manifest.json',
  '/icon-192.png',
  '/icon-512.png',
];

// API paths that should use Network-First strategy
const API_PATHS = ['/scan', '/demo/', '/alerts', '/stats', '/scans', '/health',
                   '/batch', '/serial', '/receiving'];

// ── INSTALL: Pre-cache app shell ──────────────────────────────────────────
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('[SW] Pre-caching app shell');
        return cache.addAll(APP_SHELL);
      })
      .then(() => self.skipWaiting())
  );
});

// ── ACTIVATE: Clean old caches ────────────────────────────────────────────
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys
          .filter((key) => key !== CACHE_NAME)
          .map((key) => {
            console.log('[SW] Removing old cache:', key);
            return caches.delete(key);
          })
      ))
      .then(() => self.clients.claim())
  );
});

// ── FETCH: Route requests to the right strategy ──────────────────────────
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Skip non-GET requests (POST /scan, POST /batch-report, DELETE, etc.)
  if (event.request.method !== 'GET') {
    return;
  }

  // API requests → Network-First
  if (API_PATHS.some((path) => url.pathname.startsWith(path))) {
    event.respondWith(networkFirst(event.request));
    return;
  }

  // App shell & static assets → Cache-First
  event.respondWith(cacheFirst(event.request));
});


// ── STRATEGIES ────────────────────────────────────────────────────────────

/**
 * Cache-First: Serve from cache if available, otherwise fetch from network
 * and cache the response. Used for the app shell and static assets.
 */
async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) {
    return cached;
  }

  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    // If both cache and network fail, return an offline fallback
    return offlineFallback(request);
  }
}

/**
 * Network-First: Try the network first, fall back to cache.
 * Caches successful network responses for future offline use.
 * Used for API endpoints so users always get fresh data when online.
 */
async function networkFirst(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    const cached = await caches.match(request);
    if (cached) {
      return cached;
    }
    return offlineFallback(request);
  }
}

/**
 * Returns a minimal offline JSON response when both network and cache fail.
 */
function offlineFallback(request) {
  const url = new URL(request.url);

  // For API requests, return a structured offline error
  if (API_PATHS.some((path) => url.pathname.startsWith(path))) {
    return new Response(
      JSON.stringify({
        error: {
          code: 'OFFLINE',
          message: 'You are offline. This data is not yet cached. Please connect to the internet and try again.',
        },
      }),
      {
        status: 503,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }

  // For HTML navigation requests, return a basic offline page
  if (request.headers.get('accept')?.includes('text/html')) {
    return new Response(
      `<!DOCTYPE html>
       <html lang="en">
       <head>
         <meta charset="utf-8"/>
         <meta name="viewport" content="width=device-width, initial-scale=1"/>
         <title>MedSure Vision — Offline</title>
         <style>
           body {
             font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
             display: flex; align-items: center; justify-content: center;
             min-height: 100vh; margin: 0; background: #fcf8fc; color: #1b1b1e;
             text-align: center; padding: 24px;
           }
           .offline-card {
             max-width: 400px; padding: 40px; background: #fff;
             border-radius: 16px; box-shadow: 0 4px 24px rgba(0,0,0,0.08);
           }
           .offline-icon { font-size: 48px; margin-bottom: 16px; }
           h1 { font-size: 22px; margin: 0 0 8px; }
           p { font-size: 15px; color: #464555; line-height: 1.5; }
           button {
             margin-top: 20px; padding: 12px 32px; background: #493ee5;
             color: #fff; border: none; border-radius: 9999px;
             font-size: 15px; font-weight: 600; cursor: pointer;
           }
         </style>
       </head>
       <body>
         <div class="offline-card">
           <div class="offline-icon">📡</div>
           <h1>You're Offline</h1>
           <p>MedSure Vision needs an internet connection for the first load. 
              Once cached, the app works fully offline.</p>
           <button onclick="location.reload()">Try Again</button>
         </div>
       </body>
       </html>`,
      {
        status: 503,
        headers: { 'Content-Type': 'text/html' },
      }
    );
  }

  // For other resources, return a generic 503
  return new Response('Offline', { status: 503 });
}


// ── BACKGROUND SYNC (future enhancement) ─────────────────────────────────
// When offline scans are queued, they can be retried when connectivity returns.
// This is a placeholder for future background sync support.

self.addEventListener('message', (event) => {
  if (event.data === 'skipWaiting') {
    self.skipWaiting();
  }
});
