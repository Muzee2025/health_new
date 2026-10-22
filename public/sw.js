// Retire only the old shared report cache. Private API responses stay on network.
const RETIRED_REPORT_CACHES = ['report-api-cache-v1'];
self.addEventListener('install', (event) => {
  event.waitUntil(self.skipWaiting());
});
self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    await Promise.all(RETIRED_REPORT_CACHES.map(name => caches.delete(name)));
    await self.clients.claim();
  })());
});
// No fetch handler: never cache or replay authenticated reports across users.
