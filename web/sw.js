const CACHE = "screener-v4";
const SHELL = ["/", "/static/app.js", "/static/styles.css", "/static/icon.svg", "/manifest.json"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
      // Tell every open page a new version is live so it reloads with fresh code.
      .then(() => self.clients.matchAll({ type: "window" }))
      .then((wins) => wins.forEach((w) => w.postMessage({ type: "SW_UPDATED" })))
  );
});

// Allow a page to ask the waiting worker to take over immediately.
self.addEventListener("message", (e) => {
  if (e.data && e.data.type === "SKIP_WAITING") self.skipWaiting();
});

// Network-first everywhere: fresh code & data, falling back to cache when offline.
self.addEventListener("fetch", (e) => {
  e.respondWith(
    fetch(e.request).then((res) => {
      if (e.request.method === "GET" && res && res.ok) {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy));
      }
      return res;
    }).catch(() =>
      caches.match(e.request).then((hit) => hit || caches.match("/"))
    )
  );
});
