/**
 * FOGATA — Service Worker (Fase 6 — Piloto Multiusuario)
 * Criterios de diseño y seguridad:
 * 1. Suspensión temporal de offline privado (Requisitos 11 y 12):
 *    - CACHE_STATIC ('fogata-static-v2'): App Shell técnico, CSS, JS, manifest, iconos, pantalla offline y biblioteca general de acordes.
 *    - NO almacenar en CacheStorage: canciones del usuario, Fogatas del usuario ni HTML privado de atril.
 * 2. Limpieza de 'fogata-offline' en activación para eliminar residuos previos.
 * 3. En peticiones de navegación HTML (isHtmlNavigation): Network First / Directo. Si no hay conexión, mostrar /offline/.
 * 4. Peticiones seguras únicamente: GET y HEAD. Cero colas de mutación.
 */

var CACHE_STATIC = 'fogata-static-v2';

var STATIC_ASSETS = [
  '/static/css/reset.css',
  '/static/css/fogata.css',
  '/static/js/fogata.js',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/icons/icon.svg',
  '/static/img/logo.svg',
  '/static/img/fogata_logo.svg',
  '/manifest.webmanifest',
  '/offline/'
];

// 1. Instalación: precarga del App Shell técnico en CACHE_STATIC
self.addEventListener('install', function (event) {
  event.waitUntil(
    caches.open(CACHE_STATIC).then(function (cache) {
      return Promise.all(
        STATIC_ASSETS.map(function (url) {
          return fetch(url).then(function (response) {
            if (response.ok) {
              return cache.put(url, response);
            }
          }).catch(function () {
            // Ignorar fallos individuales
          });
        })
      );
    })
  );
});

// 2. Activación: limpieza de cachés estáticos antiguos y eliminación de fogata-offline
self.addEventListener('activate', function (event) {
  event.waitUntil(
    caches.keys().then(function (cacheNames) {
      return Promise.all(
        cacheNames.map(function (cacheName) {
          // Eliminar versiones antiguas de CACHE_STATIC y eliminar fogata-offline por seguridad
          if (cacheName !== CACHE_STATIC) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});

// 3. Manejo de Peticiones de Red (Fetch)
self.addEventListener('fetch', function (event) {
  var req = event.request;

  // Exclusivamente GET y HEAD
  if (req.method !== 'GET' && req.method !== 'HEAD') {
    return;
  }

  var url = new URL(req.url);

  // A. Recursos estáticos de la aplicación (CSS, JS, iconos, manifest) -> Cache First
  if (url.pathname.indexOf('/static/') === 0 || url.pathname === '/manifest.webmanifest') {
    event.respondWith(
      caches.match(req).then(function (cached) {
        if (cached) {
          return cached;
        }
        return fetch(req).then(function (networkResponse) {
          if (networkResponse && networkResponse.ok) {
            var clone = networkResponse.clone();
            caches.open(CACHE_STATIC).then(function (cache) {
              cache.put(req, clone);
            });
          }
          return networkResponse;
        });
      })
    );
    return;
  }

  // B. Biblioteca general de digitaciones (batch público) -> Cache First
  if (url.pathname === '/canciones/diagramas/batch/') {
    event.respondWith(
      caches.match(req).then(function (cached) {
        if (cached) {
          return cached;
        }
        return fetch(req).then(function (networkResponse) {
          if (networkResponse && networkResponse.ok) {
            var clone = networkResponse.clone();
            caches.open(CACHE_STATIC).then(function (cache) {
              cache.put(req, clone);
            });
          }
          return networkResponse;
        });
      })
    );
    return;
  }

  // C. Páginas HTML / Navegación -> Network Only / Fallback seguro a /offline/
  // NO almacenar jamás HTML privado en CacheStorage durante Fase 6
  var isHtmlNavigation = (req.mode === 'navigate') ||
    (req.headers.get('accept') && req.headers.get('accept').indexOf('text/html') !== -1);

  if (isHtmlNavigation) {
    event.respondWith(
      fetch(req).catch(function () {
        return caches.match('/offline/').then(function (offlineShell) {
          if (offlineShell) {
            return offlineShell;
          }
          return new Response(
            '<!DOCTYPE html><html><head><meta charset="utf-8"><title>Fogata Offline</title>' +
            '<meta name="viewport" content="width=device-width,initial-scale=1"></head>' +
            '<body style="background:#0d0d0d;color:#fff;font-family:sans-serif;padding:24px;text-align:center;">' +
            '<h1>🔥 Fogata</h1><p>Sin conexión a internet.</p><a href="/offline/" style="color:#ff9800;">Ver Modo Offline</a></body></html>',
            { headers: { 'Content-Type': 'text/html; charset=utf-8' } }
          );
        });
      })
    );
    return;
  }

  // D. Demás peticiones GET genéricas -> Buscar en caché estático, luego red
  event.respondWith(
    caches.match(req).then(function (cached) {
      if (cached) {
        return cached;
      }
      return fetch(req);
    })
  );
});
