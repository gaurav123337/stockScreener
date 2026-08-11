import { useEffect, useState } from "react";
import { api } from "@/api/endpoints";
import { useAuth } from "@/features/auth/auth-context";

function urlBase64ToUint8Array(base64: string): Uint8Array {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const normalized = (base64 + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = window.atob(normalized);
  const output = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i += 1) output[i] = raw.charCodeAt(i);
  return output;
}

/**
 * PWA push notifications (Phase 5). Requests Notification permission, registers
 * the service worker, subscribes with the server's VAPID key and persists the
 * endpoint via /api/push/subscribe. Returns a "supported/on/off/unavailable"
 * state so the UI can show the right affordance.
 */
export function usePushNotifications() {
  const { isLoggedIn } = useAuth();
  const [permission, setPermission] = useState<NotificationPermission | "unsupported" | "prompt">(
    typeof Notification === "undefined" ? "unsupported" : Notification.permission,
  );
  const [isSubscribing, setIsSubscribing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (typeof Notification === "undefined") return;
    const handler = () => setPermission(Notification.permission);
    Notification.requestPermission().catch(() => undefined);
    window.addEventListener("notificationchange", handler);
    return () => window.removeEventListener("notificationchange", handler);
  }, []);

  const supported =
    typeof Notification !== "undefined" &&
    "serviceWorker" in navigator &&
    "PushManager" in window;

  const subscribe = async () => {
    if (!isLoggedIn || !supported) return false;
    setIsSubscribing(true);
    setError(null);
    try {
      const perm = await Notification.requestPermission();
      setPermission(perm);
      if (perm !== "granted") return false;

      const registration = await navigator.serviceWorker.ready;
      const { public_key } = await api.pushPublicKey();
      let subscription = await registration.pushManager.getSubscription();
      if (!subscription) {
        subscription = await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(public_key) as BufferSource,
        });
      }
      await api.pushSubscribe({
        endpoint: subscription.endpoint,
        p256dh: btoa(String.fromCharCode(...new Uint8Array(subscription.getKey("p256dh")!))),
        auth: btoa(String.fromCharCode(...new Uint8Array(subscription.getKey("auth")!))),
        user_agent: navigator.userAgent,
      });
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not enable notifications");
      return false;
    } finally {
      setIsSubscribing(false);
    }
  };

  const unsubscribe = async () => {
    if (!supported) return;
    try {
      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.getSubscription();
      if (subscription) {
        await api.pushUnsubscribe(subscription.endpoint);
        await subscription.unsubscribe();
      }
      setPermission("prompt");
    } catch {
      // Best-effort; the endpoint is removed server-side on next visit.
    }
  };

  return { supported, permission, isSubscribing, error, subscribe, unsubscribe };
}
