import { useCallback, useMemo, useState, type ReactNode } from "react";
import { api } from "@/api/endpoints";
import { clearAuth, getStoredUser, getToken, setStoredUser, setToken } from "@/api/client";
import { AuthContext, type AuthContextValue } from "./auth-context";
import type { UserProfile } from "@/types/api";
import { queryClient } from "@/app/queryClient";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(() => {
    const stored = getStoredUser();
    if (stored && getToken()) {
      return {
        user_id: stored.user_id,
        username: stored.username,
        display_name: stored.display_name,
        created_at: "",
        preferences: {},
      };
    }
    return null;
  });

  const isLoggedIn = user !== null && user.username !== "guest";
  const isGuest = !isLoggedIn;

  const login = useCallback(async (username: string, password: string) => {
    const result = await api.login({ username, password });
    queryClient.clear();
    setToken(result.token);
    const profile: UserProfile = {
      user_id: result.user.user_id,
      username: result.user.username,
      display_name: result.user.display_name,
      created_at: result.user.created_at,
      preferences: result.user.preferences,
    };
    setStoredUser(profile);
    setUser(profile);
  }, []);

  const register = useCallback(async (username: string, password: string, displayName?: string) => {
    const result = await api.register({ username, password, display_name: displayName });
    queryClient.clear();
    setToken(result.token);
    const profile: UserProfile = {
      user_id: result.user.user_id,
      username: result.user.username,
      display_name: result.user.display_name,
      created_at: result.user.created_at,
      preferences: result.user.preferences,
    };
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
