"use client";

import { createContext, useContext, useEffect, useState, ReactNode, useCallback, useRef } from "react";
import { api, User, setToken, clearToken, getToken } from "./api";

type AuthState = "loading" | "authenticated" | "unauthenticated";

interface AuthContextValue {
  state: AuthState;
  user: User | null;
  onboardingComplete: boolean;
  login: (email: string, password: string) => Promise<{ redirectTo: string }>;
  register: (email: string, password: string, name?: string) => Promise<{ redirectTo: string }>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>("loading");
  const [user, setUser] = useState<User | null>(null);
  const [onboardingComplete, setOnboardingComplete] = useState(false);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const refreshUser = useCallback(async () => {
    if (!getToken()) {
      if (mountedRef.current) {
        setState("unauthenticated");
        setUser(null);
        setOnboardingComplete(false);
      }
      return;
    }
    try {
      const u = await api.auth.me();
      if (!mountedRef.current) return;
      setUser(u);
      setState("authenticated");
      try {
        const ob = await api.onboarding.get();
        if (!mountedRef.current) return;
        // Onboarding is complete only when all REQUIRED fields are present.
        // Required: pay_frequency, monthly_income_range, payday_range.
        // Optional: financial_pressure, early_access_use_case, ai_help_preference.
        const requiredComplete =
          !!ob.pay_frequency &&
          !!ob.monthly_income_range &&
          !!ob.payday_range;
        setOnboardingComplete(requiredComplete);
      } catch {
        if (mountedRef.current) setOnboardingComplete(false);
      }
    } catch {
      if (!mountedRef.current) return;
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

  const logout = async () => {
    await api.auth.logout();
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