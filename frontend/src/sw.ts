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

/**
 * PWA push notifications (Phase 5) — alert delivery surface.
 * The service worker turns an incoming web-push payload into a system
 * notification. Clicking it focuses an open tab (or opens one) and routes to
 * the alert's target page.
 */
self.addEventListener("push", (event) => {
  let data: {
    title?: string;
    body?: string;
    url?: string;
    tag?: string;
  } = {};
  try {
    const parsed = event.data?.json?.();
    if (parsed && typeof parsed === "object") data = parsed;
  } catch {
    // Fall back to raw text if the payload is not JSON.
    data = { title: event.data?.text?.() ?? "stockScreener alert" };
  }
  const title = data.title ?? "stockScreener alert";
  const options: NotificationOptions = {
    body: data.body ?? "",
    tag: data.tag ?? "screener-alert",
    icon: "/pwa-192x192.png",
    badge: "/pwa-192x192.png",
    data: { url: data.url ?? "/" },
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  const url = (event.notification.data as { url?: string } | undefined)?.url ?? "/";
  event.notification.close();
  event.waitUntil(
    (async () => {
      const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
      for (const win of windows) {
        if ("focus" in win) {
          win.focus();
          void win.navigate(url);
          return;
        }
      }
      if (self.clients.openWindow) {
        await self.clients.openWindow(url);
      }
    })(),
  );
});

export {};
