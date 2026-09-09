"use client";

import Link from "next/link";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowRight, Check, ChevronLeft } from "lucide-react";
import { useState } from "react";
import { onboardingStorageKey, type OnboardingProfile } from "@/lib/onboarding";
import { api } from "@/lib/api";
import { useRouter } from "next/navigation";

const questions = [
  { key: "name", title: "What should we call you?", text: "A name helps make your ARQAU experience feel personal.", type: "text", label: "Name", placeholder: "Guest" },
  { key: "payFrequency", type: "choice", title: "How do you usually get paid?", text: "Your pay cycle helps ARQAU understand your earnings schedule.", options: ["Monthly", "Twice a month", "Weekly", "It varies"] },
  { key: "monthlyIncomeRange", type: "choice", title: "What&apos;s your usual monthly income?", text: "An approximate range is enough.", options: ["Under 150,000 ₸", "150,000-300,000 ₸", "300,000-500,000 ₸", "500,000-750,000 ₸", "750,000 ₸+"] },
  { key: "paydayRange", type: "choice", title: "When do you usually get paid?", text: "Your payday helps ARQAU understand your financial cycle.", options: ["1st-5th", "6th-15th", "16th-25th", "26th-31st", "It varies"] },
  { key: "financialPressure", type: "multi", title: "What usually puts the most pressure on your budget before payday?", text: "Choose all that apply. If nothing in particular, select &quot;Nothing in particular&quot;.", options: ["Unexpected expenses", "Regular bills", "Food & everyday spending", "Transport", "Large planned purchases", "Nothing in particular", "Other"] },
  { key: "earlyAccessUseCase", type: "choice", title: "When would early access to your earned wages be most useful?", text: "This connects your context to ARQAU&apos;s core product.", options: ["An unexpected expense", "Bills before payday", "Everyday spending", "A planned purchase", "Building a financial buffer"] },
  { key: "aiHelpPreference", type: "choice", title: "How should ARQAU help you manage your money?", text: "This sets the kind of future guidance you would find useful.", options: ["Warn me before I may run short", "Help me understand my spending", "Help me decide when accessing earned wages may make sense", "Help me build a financial buffer", "Give me a simple overview"] },
] as const;

type AnswerKey = keyof OnboardingProfile;
type Answers = Partial<OnboardingProfile>;

export default function SmartOnboarding() {
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<Answers>({ name: "Guest" });
  const [complete, setComplete] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [otherText, setOtherText] = useState("");
  const router = useRouter();
  const question = questions[step];
  const currentValue = answers[question.key as AnswerKey] ?? "";
  const canContinue = String(currentValue).trim().length > 0;

  function getSelectedArray(): string[] {
    const val = currentValue;
    if (Array.isArray(val)) return val;
    if (typeof val === "string" && val) return val.split(", ").filter(Boolean);
    return [];
  }

  function toggleOption(option: string) {
    const selected = getSelectedArray();
    if (option === "Nothing in particular") {
      setAnswers((current) => ({ ...current, [question.key]: "Nothing in particular" }));
      setOtherText("");
      return;
    }
    if (selected.includes("Nothing in particular")) {
      setAnswers((current) => ({ ...current, [question.key]: [option] }));
      return;
    }
    if (selected.includes(option)) {
      const next = selected.filter((s) => s !== option);
      setAnswers((current) => ({ ...current, [question.key]: next.join(", ") }));
      return;
    }
    setAnswers((current) => ({ ...current, [question.key]: [...selected, option].join(", ") }));
  }

  function isSelected(option: string) {
    return getSelectedArray().includes(option);
  }

  function updateAnswer(value: string) {
    setAnswers((current) => ({ ...current, [question.key]: value }));
  }

  async function finish() {
    setSaving(true);
    setError("");
    try {
      const payload: Record<string, string> = {};
      if (typeof answers.payFrequency === "string") payload.pay_frequency = answers.payFrequency;
      if (typeof answers.monthlyIncomeRange === "string") payload.monthly_income_range = answers.monthlyIncomeRange;
      if (typeof answers.paydayRange === "string") payload.payday_range = answers.paydayRange;
      if (typeof answers.financialPressure === "string") payload.financial_pressure = answers.financialPressure;
      if (typeof answers.earlyAccessUseCase === "string") payload.early_access_use_case = answers.earlyAccessUseCase;
      if (typeof answers.aiHelpPreference === "string") payload.ai_help_preference = answers.aiHelpPreference;
      await api.onboarding.save(payload);
      localStorage.setItem(onboardingStorageKey, JSON.stringify(answers));
      setComplete(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save preferences. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  if (complete) {
    return <ResultScreen profile={answers as OnboardingProfile} onContinue={() => router.push("/dashboard")} />;
  }

  return <main className="min-h-screen bg-cream px-5 py-8 sm:px-8 sm:py-10">
    <div className="mx-auto max-w-[1040px]">
      <header className="flex items-center justify-between"><Link href="/" className="text-[20px] font-extrabold tracking-[0.08em]">ARQAU</Link><span className="text-[13px] font-semibold text-ink-soft">{String(step + 1).padStart(2, "0")} / 07</span></header>
      <div className="mt-10 h-1.5 rounded-full bg-ink/[0.08]"><motion.div className="h-1.5 rounded-full bg-green-deep" animate={{ width: `${((step + 1) / questions.length) * 100}%` }} transition={{ duration: 0.4 }} /></div>
      <div className="mt-5 flex justify-between text-[12px] text-ink-soft"><span>{step < 4 ? "About you" : "Your financial priorities"}</span><span>{Math.round(((step + 1) / questions.length) * 100)}%</span></div>
      <div className="grid items-center gap-12 py-14 lg:grid-cols-[0.72fr_1.28fr] lg:py-20">
        <div className="hidden lg:block"><p className="eyebrow mb-5">Build your ARQAU profile</p><h1 className="text-[56px] font-extrabold leading-[0.98] tracking-[-0.045em]">Tell ARQAU what matters before payday.</h1><p className="mt-6 max-w-[360px] text-[16px] leading-relaxed text-ink-soft">Seven useful questions now. A better foundation for future financial guidance later.</p><div className="mt-10 border-l-2 border-green-deep pl-5 text-[14px] leading-relaxed text-ink-soft">Your answers are saved to your secure account.</div></div>
        <section className="rounded-[28px] border border-ink/[0.09] bg-white/75 p-6 shadow-[0_28px_70px_-48px_rgba(21,21,21,0.5)] sm:p-10">
          <AnimatePresence mode="wait"><motion.div key={step} initial={{ opacity: 0, x: 18 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -18 }} transition={{ duration: 0.28 }}>
            <p className="eyebrow mb-5">Question {String(step + 1).padStart(2, "0")}</p><h2 className="text-[34px] font-extrabold leading-[1.02] tracking-[-0.035em] sm:text-[46px]" dangerouslySetInnerHTML={{ __html: question.title }} /><p className="mt-5 max-w-[560px] text-[16px] leading-relaxed text-ink-soft" dangerouslySetInnerHTML={{ __html: question.text }} />
            {question.type === "text" ? <label className="mt-9 block text-[13px] font-semibold">{question.label}<input autoFocus value={String(currentValue)} onChange={(event) => updateAnswer(event.target.value)} placeholder={question.placeholder} className="mt-2 w-full rounded-[12px] border border-ink/[0.12] bg-cream px-4 py-4 text-[16px] outline-none transition-colors focus:border-green-deep" /></label> : question.type === "multi" ? <div className="mt-9 grid gap-3">{question.options?.map((option) => <button key={option} type="button" onClick={() => toggleOption(option)} className={`flex w-full items-center justify-between rounded-[14px] border px-4 py-4 text-left text-[14px] font-semibold transition-all ${isSelected(option) ? "border-green-deep bg-green-soft text-ink shadow-[0_10px_24px_-20px_rgba(47,83,56,0.5)]" : "border-ink/[0.1] bg-cream/60 text-ink-soft hover:border-green/50 hover:text-ink"}`}>{option}{isSelected(option) && <Check size={17} className="text-green-deep" />}</button>)}</div> : <div className="mt-9 grid gap-3">{question.options?.map((option) => <button key={option} type="button" onClick={() => updateAnswer(option)} className={`flex w-full items-center justify-between rounded-[14px] border px-4 py-4 text-left text-[14px] font-semibold transition-all ${currentValue === option ? "border-green-deep bg-green-soft text-ink shadow-[0_10px_24px_-20px_rgba(47,83,56,0.5)]" : "border-ink/[0.1] bg-cream/60 text-ink-soft hover:border-green/50 hover:text-ink"}`}>{option}{currentValue === option && <Check size={17} className="text-green-deep" />}</button>)}</div>}
            {question.key === "financialPressure" && isSelected("Other") && (
              <label className="mt-3 block text-[13px] font-semibold">Please describe
                <input
                  autoFocus
                  value={otherText}
                  onChange={(event) => {
                    setOtherText(event.target.value);
                    const selected = getSelectedArray().filter((s) => s !== "Other");
                    const newValue = event.target.value.trim() ? [...selected, `Other: ${event.target.value}`].join(", ") : selected.join(", ");
                    updateAnswer(newValue);
                  }}
                  placeholder="Tell us more..."
                  className="mt-2 w-full rounded-[12px] border border-ink/[0.12] bg-cream px-4 py-3 text-[14px] outline-none transition-colors focus:border-green-deep"
                />
              </label>
            )}
          </motion.div></AnimatePresence>
          {error && <div className="mt-4 rounded-[10px] border border-red-200 bg-red-50 px-4 py-3 text-[13px] text-red-700">{error}</div>}
          <div className="mt-10 flex items-center justify-between border-t border-ink/[0.08] pt-5"><button type="button" onClick={() => setStep((current) => Math.max(0, current - 1))} disabled={step === 0 || saving} className="btn-secondary disabled:pointer-events-none disabled:opacity-30"><ChevronLeft size={16} />Back</button><button type="button" onClick={() => step === questions.length - 1 ? finish() : setStep((current) => current + 1)} disabled={!canContinue || saving} className="btn-primary disabled:pointer-events-none disabled:opacity-40">{saving ? "Saving..." : step === questions.length - 1 ? "Create my profile" : "Continue"}<ArrowRight size={16} /></button></div>
        </section>
      </div>
    </div>
  </main>;
}

function ResultScreen({ profile, onContinue }: { profile: OnboardingProfile; onContinue: () => void }) {
  return <main className="min-h-screen bg-cream px-5 py-8 sm:px-8 sm:py-10"><div className="mx-auto max-w-[1040px]"><header className="flex items-center justify-between"><Link href="/" className="text-[20px] font-extrabold tracking-[0.08em]">ARQAU</Link><span className="flex items-center gap-2 text-[13px] font-semibold text-green"><Check size={16} />Profile ready</span></header><div className="grid items-center gap-12 py-16 lg:grid-cols-[0.8fr_1.2fr] lg:py-24"><div><p className="eyebrow mb-5">Your ARQAU profile is ready.</p><h1 className="text-[50px] font-extrabold leading-[0.98] tracking-[-0.045em] sm:text-[68px]">A clearer starting point, {profile.name}.</h1><p className="mt-6 max-w-[480px] text-[17px] leading-relaxed text-ink-soft">Your answers are saved to your account. Financial data will appear here once you add it.</p><button onClick={onContinue} className="btn-primary mt-8">Open dashboard <ArrowRight size={16} /></button></div><div className="rounded-[28px] border border-green/25 bg-green-soft p-6 sm:p-9"><p className="text-[12px] font-bold uppercase tracking-[0.12em] text-green-deep">Your profile</p><div className="mt-7 grid gap-5 sm:grid-cols-2">{[["Your focus", profile.aiHelpPreference], ["Your pay cycle", profile.payFrequency], ["Financial pressure", profile.financialPressure], ["Payday", profile.paydayRange]].map(([label, value]) => <div key={label}><p className="text-[12px] text-ink-soft">{label}</p><p className="mt-1 text-[15px] font-bold">{value}</p></div>)}</div></div></div></div></main>;
}
