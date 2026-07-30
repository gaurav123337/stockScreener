import { clearAuth, getStoredUser, getToken, setStoredUser, setToken } from "@/api/client";
import { api } from "@/api/endpoints";
import { queryClient } from "@/app/queryClient";
import type { UserProfile } from "@/types/api";
import { useCallback, useMemo, useState, type ReactNode } from "react";
import { AuthContext, type AuthContextValue } from "./auth-context";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(() => {
    const stored = getStoredUser();
    if (stored && getToken()) {
      return {
        user_id: stored.user_id,
        username: stored.username,
        email: null,
        display_name: stored.display_name,
        role: stored.role ?? "user",
        status: stored.status ?? "active",
        email_verified_at: null,
        created_at: "",
        last_login_at: null,
        preferences: {},
      };
    }
    return null;
  });

  const isLoggedIn = user !== null && user.username !== "guest";
  const isGuest = !isLoggedIn;

  const login = useCallback(async (email: string, password: string) => {
    const result = await api.login({ email, password });
    queryClient.clear();
    setToken(result.token);
    const profile = result.user;
    setStoredUser(profile);
    setUser(profile);
    return profile;
  }, []);

  const register = useCallback(async (email: string, password: string, confirmation: string, displayName?: string) => {
    const result = await api.register({ email, password, password_confirmation: confirmation, display_name: displayName });
    queryClient.clear();
    setToken(result.token);
    const profile = result.user;
    setStoredUser(profile);
    setUser(profile);
  }, []);

  const logout = useCallback(() => {
    clearAuth();
    queryClient.clear();
    setUser(null);
  }, []);

  const refreshUser = useCallback(async () => {
    if (!getToken()) return;
    try {
      const profile = await api.me();
      setStoredUser(profile);
      setUser(profile);
    } catch {
      // Token invalid — clear auth
      clearAuth();
      queryClient.clear();
      setUser(null);
    }
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ user, isLoggedIn, isGuest, login, register, logout, refreshUser }),
    [user, isLoggedIn, isGuest, login, register, logout, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
