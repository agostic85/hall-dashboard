/* Service worker för Kontoret-appen (PWA). Hämtar alltid senaste versionen
   från nätet; cachen används bara som reserv om nätet ligger nere. */
var CACHE = 'hd-v1';
self.addEventListener('install', function(){ self.skipWaiting(); });
self.addEventListener('activate', function(e){ e.waitUntil(self.clients.claim()); });
self.addEventListener('fetch', function(e){
  if (e.request.mode !== 'navigate') return;
  e.respondWith(
    fetch(e.request.url, {cache: 'no-store'}).then(function(res){
      var copy = res.clone();
      caches.open(CACHE).then(function(c){ c.put(e.request.url, copy); });
      return res;
    }).catch(function(){ return caches.match(e.request.url); })
  );
});
