/// <reference lib="webworker" />
import { precacheAndRoute, cleanupOutdatedCaches } from "workbox-precaching";

declare const self: ServiceWorkerGlobalScope;

/**
 * Service worker — preserves the legacy behavior:
 *  - precache the app shell (injected by vite-plugin-pwa at build time)
 *  - network-first for everything else, falling back to cache offline
 *  - auto-activate and notify clients so open tabs reload with fresh code
 */
precacheAndRoute(self.__WB_MANIFEST);
cleanupOutdatedCaches();

self.addEventListener("install", () => {
  void self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      await self.clients.claim();
      const windows = await self.clients.matchAll({ type: "window" });
      for (const win of windows) win.postMessage({ type: "SW_UPDATED" });
    })(),
  );
});

self.addEventListener("message", (event) => {
  if ((event.data as { type?: string } | null)?.type === "SKIP_WAITING") {
    void self.skipWaiting();
  }
});

self.addEventListener("fetch", (event) => {
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (event.request.method === "GET" && response.ok) {
          const copy = response.clone();
          void caches.open("screener-runtime").then((cache) => cache.put(event.request, copy));
        }
        return response;
      })
      .catch(async () => {
        const hit = await caches.match(event.request);
        return hit ?? (await caches.match("/")) ?? Response.error();
      }),
  );
});

export {};
