"use client";

import { createContext, useContext, useEffect, useState, ReactNode, useCallback } from "react";
import { api, User, setToken, clearToken, getToken } from "./api";

type AuthState = "loading" | "authenticated" | "unauthenticated";

interface AuthContextValue {
  state: AuthState;
  user: User | null;
  onboardingComplete: boolean;
  login: (email: string, password: string) => Promise<{ redirectTo: string }>;
  register: (email: string, password: string, name?: string) => Promise<{ redirectTo: string }>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>("loading");
  const [user, setUser] = useState<User | null>(null);
  const [onboardingComplete, setOnboardingComplete] = useState(false);

  const refreshUser = useCallback(async () => {
    if (!getToken()) {
      setState("unauthenticated");
      setUser(null);
      setOnboardingComplete(false);
      return;
    }
    try {
      const u = await api.auth.me();
      setUser(u);
      setState("authenticated");
      try {
        const ob = await api.onboarding.get();
        setOnboardingComplete(!!ob.pay_frequency);
      } catch {
        setOnboardingComplete(false);
      }
    } catch {
      clearToken();
      setUser(null);
      setOnboardingComplete(false);
      setState("unauthenticated");
    }
  }, []);

  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  const login = async (email: string, password: string) => {
    const { access_token } = await api.auth.login(email, password);
    setToken(access_token);
    await refreshUser();
    return { redirectTo: onboardingComplete ? "/dashboard" : "/onboarding" };
  };

  const register = async (email: string, password: string, name?: string) => {
    await api.auth.register(email, password, name);
    return login(email, password);
  };

  const logout = () => {
    clearToken();
    setUser(null);
    setOnboardingComplete(false);
    setState("unauthenticated");
  };

  return (
    <AuthContext.Provider value={{ state, user, onboardingComplete, login, register, logout, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
