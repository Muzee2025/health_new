const CACHE_NAME = 'report-api-cache-v1';
const API_URLS = ['/api/student/report/analysis'];

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(clients.claim());
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  
  if (event.request.method === 'GET' && 
      API_URLS.some(api => url.pathname.endsWith(api)) && 
      !url.pathname.includes('/refresh')) {
    
    event.respondWith(
      caches.open(CACHE_NAME).then(async (cache) => {
        const cachedResponse = await cache.match(event.request);
        
        const fetchPromise = fetch(event.request).then((networkResponse) => {
          if (networkResponse.ok) {
            cache.put(event.request, networkResponse.clone());
          }
          return networkResponse;
        }).catch(() => {
          // fallback
        });

        return cachedResponse || fetchPromise;
      })
    );
  }
});
