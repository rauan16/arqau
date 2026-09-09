"use client";

import Link from "next/link";
import { ArrowRight, Check, ChevronLeft, ChevronRight, Building2, Mail } from "lucide-react";
import { useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { useTranslation } from "@/lib/language-context";
import { useRouter } from "next/navigation";

const inputClass = "mt-2 w-full rounded-[10px] border border-ink/[0.12] bg-cream px-4 py-3 text-[14px] outline-none transition-colors focus:border-orange-deep focus-ring";

export function AuthPage({ mode }: { mode: "login" | "signup" }) {
  const isLogin = mode === "login";
  const { t } = useTranslation();
  const { login, register } = useAuth();
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { redirectTo } = isLogin
        ? await login(email, password)
        : await register(email, password, name || undefined);
      router.push(redirectTo);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : t.auth.errorRequired);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-cream px-5 py-8 sm:px-8">
      <div className="mx-auto flex min-h-[calc(100vh-64px)] max-w-[1120px] items-center justify-center">
        <div className="grid w-full overflow-hidden rounded-[28px] border border-ink/[0.08] bg-white/70 shadow-[0_30px_80px_-45px_rgba(21,21,21,0.45)] lg:grid-cols-[0.8fr_1.2fr]">
          <div className="hidden bg-ink p-12 text-cream lg:block">
            <Link href="/" className="text-[20px] font-extrabold tracking-[0.08em]">ARQAU</Link>
            <div className="mt-32 max-w-[360px]">
              <p className="eyebrow text-green-2">A clearer financial decision</p>
              <h1 className="mt-5 text-[52px] font-extrabold leading-[0.98] tracking-[-0.04em]">Earned income, in context.</h1>
              <p className="mt-6 text-[16px] leading-relaxed text-cream/65">Your salary, expenses and reserve in one calm workspace.</p>
            </div>
          </div>
          <div className="p-7 sm:p-12">
            <Link href="/" className="text-[19px] font-extrabold tracking-[0.08em] lg:hidden">ARQAU</Link>
            <div className="mx-auto max-w-[420px] lg:mt-10">
              <p className="eyebrow mb-4">{isLogin ? t.auth.loginTitle : t.auth.signupTitle}</p>
              <h2 className="text-[38px] font-extrabold leading-none tracking-[-0.04em]">{isLogin ? t.auth.loginSubtitle : t.auth.signupSubtitle}</h2>
              <p className="mt-4 text-[15px] leading-relaxed text-ink-soft">{isLogin ? "Continue to your personal finance workspace." : "Create an account to access your earned wages securely."}</p>
              {error && (
                <div className="mt-4 rounded-[10px] border border-red-200 bg-red-50 px-4 py-3 text-[13px] text-red-700">
                  {error}
                </div>
              )}
              <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
                <label className="block text-[13px] font-semibold">
                  {t.auth.email}
                  <input
                    required
                    type="email"
                    placeholder="you@example.com"
                    className={inputClass}
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    disabled={loading}
                  />
                </label>
                <label className="block text-[13px] font-semibold">
                  {t.auth.password}
                  <input
                    required
                    type="password"
                    placeholder="••••••••"
                    className={inputClass}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    disabled={loading}
                  />
                </label>
                {!isLogin && (
                  <label className="block text-[13px] font-semibold">
                    {t.auth.name}
                    <input
                      type="text"
                      placeholder="Guest"
                      className={inputClass}
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      disabled={loading}
                    />
                  </label>
                )}
                <button className="btn-primary w-full justify-center" type="submit" disabled={loading}>
                  {loading ? (isLogin ? "Signing in..." : "Creating account...") : (isLogin ? t.auth.loginButton : t.auth.signupButton)}
                  {!loading && <ArrowRight size={16} />}
                </button>
              </form>
              <p className="mt-7 text-center text-[13px] text-ink-soft">
                {isLogin ? t.auth.noAccount : t.auth.hasAccount}{" "}
                <Link className="font-bold text-orange" href={isLogin ? "/signup" : "/login"}>
                  {isLogin ? t.auth.switchSignup : t.auth.switchLogin}
                </Link>
              </p>
              <div className="mt-10 border-t border-ink/[0.08] pt-5 text-center">
                <Link href="/business/register" className="text-[13px] font-semibold text-ink-soft hover:text-orange">
                  Register a business instead →
                </Link>
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}

export function OnboardingPage() {
  const [step, setStep] = useState(1);
  const [done, setDone] = useState(false);
  const [name, setName] = useState("");
  const [priority, setPriority] = useState("");

  if (done) {
    return (
      <main className="min-h-screen bg-cream px-5 py-8 sm:px-8">
        <div className="mx-auto max-w-[480px] text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-green text-cream">
            <Check />
          </div>
          <p className="eyebrow mt-8">Your workspace is ready</p>
          <h1 className="mt-4 text-[48px] font-extrabold leading-none tracking-[-0.04em]">A clearer start.</h1>
          <p className="mt-5 text-[16px] leading-relaxed text-ink-soft">Your preferences are saved. Add financial data later to unlock more features.</p>
          <Link href="/dashboard" className="btn-primary mt-8">
            Open dashboard <ArrowRight size={16} />
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-cream px-5 py-10 sm:px-8">
      <div className="mx-auto max-w-[720px]">
        <div className="flex items-center justify-between">
          <Link href="/" className="text-[20px] font-extrabold tracking-[0.08em]">ARQAU</Link>
          <span className="text-[13px] text-ink-soft">Step {step} of 2</span>
        </div>
        <div className="mt-12 h-1 rounded-full bg-ink/[0.08]">
          <div className="h-1 rounded-full bg-orange transition-all" style={{ width: `${(step / 2) * 100}%` }} />
        </div>
        <div className="mt-16 rounded-[26px] border border-ink/[0.08] bg-white/70 p-7 sm:p-12">
          <p className="eyebrow mb-4">Personalize ARQAU</p>
          <h1 className="text-[44px] font-extrabold leading-none tracking-[-0.04em]">
            {step === 1 ? "What should we call you?" : "What matters most right now?"}
          </h1>
          <p className="mt-5 text-[16px] leading-relaxed text-ink-soft">
            {step === 1 ? "A name helps make your workspace feel like yours." : "Choose one priority. You can change it later."}
          </p>

          {step === 1 && (
            <label className="mt-8 block text-[13px] font-semibold">
              Name
              <input
                autoFocus
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Guest"
                className={inputClass}
              />
            </label>
          )}

          {step === 2 && (
            <div className="mt-8 grid gap-3 sm:grid-cols-3">
              {["Build a reserve", "Understand spending", "Access earned wages"].map((item) => (
                <button
                  key={item}
                  type="button"
                  onClick={() => setPriority(item)}
                  className={`rounded-[14px] border px-4 py-4 text-left text-[14px] font-semibold transition-all ${
                    priority === item
                      ? "border-orange-deep bg-orange-soft text-ink shadow-[0_10px_24px_-20px_rgba(47,83,56,0.5)]"
                      : "border-ink/[0.1] bg-cream/60 text-ink-soft hover:border-orange/50 hover:text-ink"
                  }`}
                >
                  {item}
                </button>
              ))}
            </div>
          )}

          <div className="mt-10 flex justify-between">
            <button
              type="button"
              className="btn-secondary"
              disabled={step === 1}
              onClick={() => setStep((value) => Math.max(1, value - 1))}
            >
              <ChevronLeft size={16} />
              Back
            </button>
            <button
              type="button"
              className="btn-primary"
              disabled={step === 1 ? !name.trim() : !priority}
              onClick={() => (step === 2 ? setDone(true) : setStep((value) => value + 1))}
            >
              {step === 2 ? "Open dashboard" : "Continue"}
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}

export function BusinessRegistration() {
  const [step, setStep] = useState(1);
  const [submitted, setSubmitted] = useState(false);

  if (submitted) {
    return (
      <main className="min-h-screen bg-cream px-5 py-8 sm:px-8">
        <div className="mx-auto max-w-[520px] text-center">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-green text-cream">
            <Check />
          </div>
          <p className="eyebrow mt-8">Application submitted</p>
          <h1 className="mt-4 text-[48px] font-extrabold leading-none tracking-[-0.04em]">A more flexible payroll experience starts here.</h1>
          <p className="mt-5 text-[16px] leading-relaxed text-ink-soft">We&apos;ll review your business information and get back to you.</p>
          <Link href="/" className="btn-primary mt-8">
            Back to website <ArrowRight size={16} />
          </Link>
        </div>
      </main>
    );
  }

  const steps = ["Business information", "Company details", "Contact", "Product needs", "Confirmation"];

  return (
    <main className="min-h-screen bg-cream px-5 py-8 sm:px-8">
      <div className="mx-auto max-w-[980px]">
        <div className="flex items-center justify-between">
          <Link href="/" className="text-[20px] font-extrabold tracking-[0.08em]">ARQAU</Link>
          <Link href="/" className="text-[13px] text-ink-soft">Back to website</Link>
        </div>
        <div className="mt-12 grid gap-10 lg:grid-cols-[0.7fr_1.3fr]">
          <aside>
            <p className="eyebrow">For business</p>
            <h1 className="mt-4 text-[46px] font-extrabold leading-none tracking-[-0.04em]">Bring earned wage access to your team.</h1>
            <div className="mt-10 space-y-3">
              {steps.map((item, index) => (
                <div
                  key={item}
                  className={`flex items-center gap-3 text-[13px] ${step === index + 1 ? "font-bold text-ink" : "text-ink-soft"}`}
                >
                  <span
                    className={`flex h-7 w-7 items-center justify-center rounded-full border ${
                      step > index + 1
                        ? "border-orange bg-green text-cream"
                        : step === index + 1
                        ? "border-orange-deep bg-orange text-cream"
                        : "border-ink/15"
                    }`}
                  >
                    {step > index + 1 ? <Check size={14} /> : index + 1}
                  </span>
                  {item}
                </div>
              ))}
            </div>
          </aside>
          <section className="rounded-[26px] border border-ink/[0.08] bg-white/70 p-7 sm:p-10">
            <p className="text-[13px] text-ink-soft">Step {step} of 5</p>
            <h2 className="mt-3 text-[32px] font-extrabold">{steps[step - 1]}</h2>
            <div className="mt-8 space-y-5">
              {step < 4 ? (
                <>
                  <Field
                    icon={<Building2 size={16} />}
                    label={step === 1 ? "Business name" : step === 2 ? "Number of employees" : "Contact person"}
                    placeholder={step === 1 ? "Acme Company" : step === 2 ? "1284" : "Your name"}
                  />
                  <Field
                    icon={<Mail size={16} />}
                    label={step === 1 ? "Work email" : step === 2 ? "Average monthly payroll" : "Work email"}
                    placeholder={step === 1 ? "team@company.com" : step === 2 ? "38,400,000 ₸" : "you@company.com"}
                  />
                </>
              ) : step === 4 ? (
                <div className="grid gap-3">
                  {["Employee financial wellness", "Salary management", "Earned wage access", "Financial analytics", "AI insights"].map((item) => (
                    <label key={item} className="flex items-center gap-3 rounded-[12px] border border-ink/[0.1] p-4 text-[14px]">
                      <input type="checkbox" defaultChecked />
                      {item}
                    </label>
                  ))}
                </div>
              ) : (
                <div className="rounded-[16px] bg-cream-orange p-5 text-[14px] leading-relaxed text-ink-soft">
                  Your application includes business information, company details, contact information and selected ARQAU product needs.
                </div>
              )}
            </div>
            <div className="mt-10 flex justify-between">
              <button
                className="btn-secondary"
                disabled={step === 1}
                onClick={() => setStep((value) => Math.max(1, value - 1))}
              >
                <ChevronLeft size={16} />
                Back
              </button>
              <button
                className="btn-primary"
                onClick={() => (step === 5 ? setSubmitted(true) : setStep((value) => value + 1))}
              >
                {step === 5 ? "Submit application" : "Continue"}
                <ChevronRight size={16} />
              </button>
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}

function Field({ label, placeholder, icon }: { label: string; placeholder: string; icon: React.ReactNode }) {
  return (
    <label className="block text-[13px] font-semibold">
      <span className="flex items-center gap-2">{icon}{label}</span>
      <input required placeholder={placeholder} className={inputClass} />
    </label>
  );
}
