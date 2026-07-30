import type { UserProfile } from "@/types/api";
import { createContext, useContext } from "react";

export interface AuthContextValue {
  user: UserProfile | null;
  isLoggedIn: boolean;
  isGuest: boolean;
  login: (email: string, password: string) => Promise<UserProfile>;
  register: (email: string, password: string, confirmation: string, displayName?: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue>({
  user: null,
  isLoggedIn: false,
  isGuest: true,
  login: async () => ({
    user_id: "",
    username: "",
    email: null,
    display_name: null,
    role: "user",
    status: "active",
    email_verified_at: null,
    created_at: "",
    last_login_at: null,
    preferences: {},
  }),
  register: async () => {},
  logout: () => {},
  refreshUser: async () => {},
});

export function useAuth(): AuthContextValue {
  return useContext(AuthContext);
}
