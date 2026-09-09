"use client";

import { useTranslation, useLocale } from "@/lib/language-context";

export default function LanguageSwitcher() {
  const { locale, setLocale } = useTranslation();

  return (
    <div className="flex items-center gap-1 rounded-full border border-ink/[0.1] bg-cream/80 p-0.5">
      <button
        type="button"
        onClick={() => setLocale("en")}
        className={`rounded-full px-2.5 py-1 text-[11px] font-bold transition-colors ${
          locale === "en" ? "bg-orange text-cream" : "text-ink-soft hover:text-ink"
        }`}
      >
        EN
      </button>
      <button
        type="button"
        onClick={() => setLocale("ru")}
        className={`rounded-full px-2.5 py-1 text-[11px] font-bold transition-colors ${
          locale === "ru" ? "bg-orange text-cream" : "text-ink-soft hover:text-ink"
        }`}
      >
        RU
      </button>
    </div>
  );
}
