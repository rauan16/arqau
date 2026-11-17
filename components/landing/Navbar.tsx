"use client";

import { useEffect, useState } from "react";
import { Menu, X } from "lucide-react";
import LanguageSwitcher from "@/components/app/LanguageSwitcher";
import BrandLogo from "@/components/ui/BrandLogo";
import { useTranslation } from "@/lib/language-context";

const links = [
  { key: "product", href: "#product" },
  { key: "solutions", href: "#solutions" },
  { key: "pricing", href: "#pricing" },
  { key: "about", href: "#about" },
  { key: "faq", href: "#faq" },
] as const;

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);
  const { t } = useTranslation();

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const labels = t.nav as (typeof t)["nav"];

  return (
    <header
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled || open ? "bg-white/90 backdrop-blur-md border-b border-border" : "bg-transparent"
      }`}
    >
      <div className="container-arqau flex h-[84px] items-center justify-between gap-6">
        <a href="#top" onClick={() => setOpen(false)} className="flex items-center gap-2.5 focus-ring" aria-label={t.brand}>
          <BrandLogo size={48} />
          <span className="text-[20px] font-extrabold tracking-[-0.02em] text-ink">{t.brand}</span>
        </a>

        <nav className="hidden items-center gap-8 lg:flex">
          {links.map((l) => (
            <a
              key={l.href}
              href={l.href}
              onClick={() => setOpen(false)}
              className="text-[15px] font-semibold text-ink-soft transition-colors hover:text-ink focus-ring"
            >
              {labels[l.key]}
            </a>
          ))}
        </nav>

        <div className="hidden items-center gap-4 lg:flex">
          <LanguageSwitcher />
          <a
            href="/login"
            className="rounded-full border-[1.5px] border-border-strong px-6 py-[11px] text-[15px] font-bold text-ink transition-colors hover:border-ink focus-ring"
          >
            {labels.login}
          </a>
          <a href="/signup" onClick={() => setOpen(false)} className="btn-nav">
            {labels.cta} <span className="btn-arrow">→</span>
          </a>
        </div>

        <button
          className="flex h-11 w-11 items-center justify-center rounded-full border-[1.5px] border-border-strong text-ink lg:hidden focus-ring"
          aria-label={open ? labels.closeMenu : labels.openMenu}
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>

      {open && (
        <div className="border-t border-border bg-white px-6 pb-8 pt-4 lg:hidden">
          <nav className="flex flex-col">
            {links.map((l) => (
              <a
                key={l.href}
                href={l.href}
                onClick={() => setOpen(false)}
                className="border-b border-border py-4 text-[16px] font-semibold text-ink"
              >
                {labels[l.key]}
              </a>
            ))}
          </nav>
          <div className="mt-6 flex flex-col gap-3">
            <a
              href="/login"
              onClick={() => setOpen(false)}
              className="btn-outline w-full"
            >
              {labels.login}
            </a>
            <a href="/signup" onClick={() => setOpen(false)} className="btn-primary w-full">
              {labels.cta} <span className="btn-arrow">→</span>
            </a>
          </div>
          <div className="mt-5">
            <LanguageSwitcher />
          </div>
        </div>
      )}
    </header>
  );
}
