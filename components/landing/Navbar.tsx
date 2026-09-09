"use client";

import { useEffect, useState } from "react";
import { Menu, X } from "lucide-react";
import LanguageSwitcher from "@/components/app/LanguageSwitcher";
import { useTranslation } from "@/lib/language-context";

const links = [
  { labelKey: "landing.howItWorksTitle", href: "#how-it-works" },
  { labelKey: "navAI", href: "#ai-assistant" },
  { labelKey: "landing.employerTitle", href: "#employers" },
];

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

  return (
    <header
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-300 ${
        scrolled ? "bg-cream/85 backdrop-blur-md border-b border-ink/[0.06]" : "bg-transparent"
      }`}
    >
      <div className="container-arqau flex items-center justify-between h-[76px]">
        <a href="#top" className="text-[19px] font-extrabold tracking-[0.08em] text-ink focus-ring">
          ARQAU
        </a>

        <nav className="hidden md:flex items-center gap-9">
          {links.map((l) => (
            <a
              key={l.href}
              href={l.href}
              className="text-[14.5px] text-ink-soft hover:text-ink transition-colors focus-ring"
            >
              {t[l.labelKey as keyof typeof t] as string}
            </a>
          ))}
          <a href="/login" onClick={() => setOpen(false)} className="py-4 text-[15px] font-semibold text-ink border-b border-ink/[0.08]">Login</a>
        </nav>

        <div className="hidden items-center gap-5 md:flex">
          <a href="/login" className="text-[14px] font-semibold text-ink-soft hover:text-ink">Login</a>
          <a href="/signup" className="btn-primary">Get started <span className="btn-arrow">→</span></a>
          <LanguageSwitcher />
        </div>

        <button
          className="md:hidden focus-ring"
          aria-label={open ? "Close menu" : "Open menu"}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? <X size={24} /> : <Menu size={24} />}
        </button>
      </div>

      {open && (
        <div className="md:hidden bg-cream border-t border-ink/[0.08] px-6 pb-7 pt-3 flex flex-col gap-1 shadow-[0_24px_40px_-32px_rgba(21,21,21,0.55)]">
          {links.map((l) => (
            <a key={l.href} href={l.href} onClick={() => setOpen(false)} className="py-3 text-[15px] font-medium text-ink-soft">
              {t[l.labelKey as keyof typeof t] as string}
            </a>
          ))}
          <a href="/login" onClick={() => setOpen(false)} className="py-3 text-[15px] font-medium text-ink-soft">Login</a>
          <a href="/signup" onClick={() => setOpen(false)} className="btn-primary mt-2 w-fit">Get started <span className="btn-arrow">→</span></a>
          <div className="mt-2"><LanguageSwitcher /></div>
        </div>
      )}
    </header>
  );
}