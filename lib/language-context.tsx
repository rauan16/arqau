"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from "react";
import { locales, Locale } from "@/lib/i18n";

type LanguageContextValue = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: typeof locales.en;
};

const LanguageContext = createContext<LanguageContextValue | null>(null);

const STORAGE_KEY = "arqau-locale";

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("en");

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "en" || stored === "ru") {
      setLocaleState(stored);
    }
  }, []);

  function setLocale(value: Locale) {
    setLocaleState(value);
    localStorage.setItem(STORAGE_KEY, value);
  }

  return (
    <LanguageContext.Provider value={{ locale, setLocale, t: locales[locale] as typeof locales.en }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useTranslation() {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error("useTranslation must be used within LanguageProvider");
  return ctx;
}

export function useLocale() {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error("useLocale must be used within LanguageProvider");
  return ctx.locale;
}
