// app/static/sw.js
// Service worker minimal : rend l'application installable et garde une page
// de secours quand le reseau est absent.
//
// Volontairement conservateur : on ne met en cache que les ressources
// statiques (icones, logo). Les pages et les appels API passent toujours par
// le reseau, pour ne jamais afficher un tableau de bord ou des offres perimes.

const CACHE = 'nobilisx-v1';

const PRECACHE = [
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/icons/apple-touch-icon.png',
  '/static/logo.png',
  '/static/manifest.webmanifest',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE)
      .then((cache) => cache.addAll(PRECACHE))
      .then(() => self.skipWaiting())
      .catch(() => self.skipWaiting()) // une icone manquante ne doit pas bloquer l'install
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const { request } = event;

  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // Jamais de cache sur l'API ni sur l'espace admin : les donnees doivent
  // etre fraiches (abonnements, validations, offres).
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/static/admin')) {
    return;
  }

  // Ressources statiques : cache d'abord, reseau en secours.
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(request).then((cached) => cached || fetch(request).then((response) => {
        if (response && response.status === 200) {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(request, copy));
        }
        return response;
      }))
    );
    return;
  }

  // Navigation : reseau d'abord, derniere version connue si hors ligne.
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put('/', copy));
          return response;
        })
        .catch(() => caches.match('/').then((cached) => cached || new Response(
          '<!doctype html><meta charset="utf-8"><title>NobilisX</title>'
          + '<body style="font-family:system-ui;text-align:center;padding:60px 20px;background:#fff;">'
          + '<img src="/static/icons/icon-192.png" width="96" height="96" alt="">'
          + '<h1 style="font-size:20px;color:#1e1b4b;">Hors connexion</h1>'
          + '<p style="color:#64748b;">Reconnectez-vous pour consulter vos opportunites.</p>',
          { headers: { 'Content-Type': 'text/html; charset=utf-8' } }
        )))
    );
  }
});
