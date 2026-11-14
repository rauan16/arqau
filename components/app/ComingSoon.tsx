"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowRight, Mail, CheckCircle } from "lucide-react";
import { useTranslation } from "@/lib/language-context";
import BrandLogo from "@/components/ui/BrandLogo";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function ComingSoon() {
  const { t } = useTranslation();
  const a = t.auth;
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (!EMAIL_RE.test(email.trim())) {
      setError(a.comingSoonError);
      return;
    }
    setSubmitted(true);
    setEmail("");
  }

  return (
    <main className="min-h-screen bg-cream px-5 py-8 sm:px-8">
      <div className="mx-auto flex min-h-[calc(100vh-64px)] max-w-[1120px] items-center justify-center">
        <div className="grid w-full overflow-hidden rounded-[28px] border border-ink/[0.08] bg-white/70 shadow-[0_30px_80px_-45px_rgba(21,21,21,0.45)] lg:grid-cols-[0.8fr_1.2fr]">
          <div className="hidden bg-ink p-12 text-cream lg:block">
            <Link href="/" className="text-[20px] font-extrabold tracking-[0.08em]">ARQAU</Link>
            <div className="mt-32 max-w-[360px]">
              <p className="eyebrow text-orange-2">{a.comingSoonTitle}</p>
              <h1 className="mt-5 text-[52px] font-extrabold leading-[0.98] tracking-[-0.04em]">{a.comingSoonTitle}</h1>
              <p className="mt-6 text-[16px] leading-relaxed text-cream/65 whitespace-pre-line">{a.comingSoonDescription}</p>
            </div>
          </div>
          <div className="p-7 sm:p-12">
            <Link href="/" className="flex items-center"><BrandLogo size={42} /></Link>
            <div className="mx-auto max-w-[420px] lg:mt-10">
              {!submitted ? (
                <>
                  <p className="eyebrow mb-4">{a.comingSoonTitle}</p>
                  <h2 className="text-[38px] font-extrabold leading-none tracking-[-0.04em]">{a.comingSoonTitle}</h2>
                  <p className="mt-4 text-[15px] leading-relaxed text-ink-soft whitespace-pre-line">{a.comingSoonDescription}</p>
                  <form className="mt-8 space-y-5" onSubmit={handleSubmit} noValidate>
                    <label className="block text-[13px] font-semibold" htmlFor="early-email">
                      {a.comingSoonEmailLabel}
                      <input
                        id="early-email"
                        required
                        type="email"
                        autoComplete="email"
                        placeholder={a.comingSoonEmailPlaceholder}
                        className="mt-2 w-full rounded-[10px] border border-ink/[0.12] bg-cream px-4 py-3 text-[14px] outline-none transition-colors focus:border-orange-deep focus-ring"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                      />
                    </label>
                    {error && (
                      <p className="text-[13px] font-medium text-red-600" role="alert">{error}</p>
                    )}
                    <button className="btn-primary w-full justify-center" type="submit">
                      {a.comingSoonButton} <ArrowRight size={16} />
                    </button>
                  </form>
                  <p className="mt-7 text-center text-[13px] text-ink-soft">
                    <Link href="/demo" className="font-bold text-orange hover:underline">
                      {a.comingSoonDemoLink}
                    </Link>
                  </p>
                </>
              ) : (
                <div className="text-center py-12">
                  <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-orange text-cream">
                    <CheckCircle size={24} />
                  </div>
                  <p className="eyebrow mt-8">ARQAU</p>
                  <h1 className="mt-4 text-[38px] font-extrabold leading-none tracking-[-0.04em]">{a.comingSoonSuccess}</h1>
                  <p className="mt-6 text-[15px] leading-relaxed text-ink-soft">We'll be in touch soon.</p>
                  <div className="mt-10 flex flex-col gap-3 sm:flex-row sm:justify-center">
                    <Link href="/demo" className="btn-primary justify-center">
                      {a.demoCta} <ArrowRight size={16} />
                    </Link>
                    <Link href="/login" className="btn-secondary justify-center">
                      {a.loginButton}
                    </Link>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}