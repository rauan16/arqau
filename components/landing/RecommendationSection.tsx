"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { ArrowRight, BarChart3, CalendarClock, HelpCircle, ShieldCheck } from "lucide-react";
import { scenario, formatTenge } from "@/lib/demoData";
import { useTranslation } from "@/lib/language-context";
import { easeOut, fadeUp } from "@/lib/animations";

const SLIDER_MAX = scenario.available;
const SAFE_AMOUNT = scenario.recommended;
const UPCOMING_7D = 32000;
const REGULAR_SPENDING = 48000;

function fill(template: string, values: Record<string, string>) {
  return Object.entries(values).reduce(
    (text, [key, value]) => text.replace(`{${key}}`, value),
    template,
  );
}

export default function RecommendationSection() {
  const { t } = useTranslation();
  const l = t.landing;
  const [demoAmount, setDemoAmount] = useState(SAFE_AMOUNT);
  const [whyOpen, setWhyOpen] = useState(false);

  // The demo slider is the visitor's selection; the headline recommendation is
  // bounded by the existing safe amount, so the two never contradict each other.
  const exceedsSafeAmount = demoAmount > SAFE_AMOUNT;
  const recommendedAmount = exceedsSafeAmount ? SAFE_AMOUNT : demoAmount;
  const percent = (demoAmount / SLIDER_MAX) * 100;

  const factors = [
    { icon: CalendarClock, label: l.aiRecommendationsUpcoming, value: -UPCOMING_7D },
    { icon: BarChart3, label: l.aiRecommendationsRegular, value: REGULAR_SPENDING },
    { icon: ShieldCheck, label: l.aiRecommendationsSafety, value: scenario.recommended, strong: true },
  ];

  return (
    <section id="ai" className="bg-near-black py-16 text-cream sm:py-20 lg:py-24">
      <div className="container-arqau">
        <div className="grid items-start gap-10 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-16">
          <div className="max-w-[520px] lg:pt-3">
            <motion.span {...fadeUp(0)} className="pill-badge mb-6 bg-orange/15 text-orange">
              {l.aiRecommendationsEyebrow}
            </motion.span>

            <motion.h2
              {...fadeUp(0.08)}
              className="max-w-[12ch] text-[34px] font-extrabold leading-[1.08] tracking-normal text-white text-balance sm:text-[44px] lg:text-[48px]"
            >
              {l.aiRecommendationsTitleLead}
              <span className="font-serif font-medium italic text-orange">{l.aiRecommendationsTitleHighlight}</span>
              {l.aiRecommendationsTitleTail}
            </motion.h2>

            <motion.p
              {...fadeUp(0.16)}
              className="mt-5 max-w-[460px] text-[16px] leading-[1.7] text-white/65 sm:text-[17px]"
            >
              {l.aiRecommendationsSubtitle}
            </motion.p>

            <motion.a
              {...fadeUp(0.24)}
              href="#product"
              className="btn-primary mt-7"
            >
              {l.aiRecommendationsCta} <ArrowRight size={17} className="btn-arrow" />
            </motion.a>
          </div>

          {/* right: calculator card */}
          <motion.div
            initial={{ opacity: 0, y: 32 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-80px" }}
            transition={{ duration: 0.65, ease: easeOut }}
            className="border-y border-white/20 py-6 sm:py-8"
          >
            <div className="flex flex-wrap items-start justify-between gap-4 border-b border-white/15 pb-6">
              <div>
                <p className="text-[15px] font-semibold text-white/80">{l.aiRecommendationsRecommended}</p>
                <p className="numbers mt-2 text-[38px] font-extrabold leading-none text-white sm:text-[44px]">
                  {formatTenge(recommendedAmount)}
                </p>
                {exceedsSafeAmount && (
                  <p className="mt-2 max-w-[300px] text-[12.5px] font-semibold leading-snug text-orange">
                    {fill(l.aiRecommendationsAboveSafe, {
                      selected: formatTenge(demoAmount),
                      safe: formatTenge(SAFE_AMOUNT),
                    })}
                  </p>
                )}
              </div>
              <button
                type="button"
                onClick={() => setWhyOpen((v) => !v)}
                aria-expanded={whyOpen}
                aria-controls="ai-why-answer"
                className="flex items-center gap-2 border-b border-orange/50 py-2 text-[13px] font-bold text-orange transition-colors hover:border-orange focus-ring"
              >
                <HelpCircle size={14} />
                {l.aiRecommendationsWhy}
              </button>
            </div>

            {whyOpen && (
              <p
                id="ai-why-answer"
                className="mt-4 border-l-2 border-orange/60 pl-4 text-[13.5px] leading-relaxed text-white/70"
              >
                {l.aiRecommendationsWhyAnswer}
              </p>
            )}

            {/* illustrative demo slider — clearly separated from the fixed recommendation */}
            <div className="py-6">
              <div className="mb-3 flex items-center justify-between text-[13px] font-semibold">
                <span className="text-white/60">{l.aiRecommendationsSliderDemo}</span>
                <span className="numbers text-orange">{formatTenge(demoAmount)}</span>
              </div>
              <input
                type="range"
                min={0}
                max={SLIDER_MAX}
                step={5000}
                value={demoAmount}
                onChange={(e) => setDemoAmount(Number(e.target.value))}
                aria-label={l.aiRecommendationsSliderDemo}
                aria-valuetext={formatTenge(demoAmount)}
                className="slider-orange"
                style={{
                  background: `linear-gradient(to right, var(--orange) 0%, var(--orange) ${percent}%, rgba(255,255,255,0.14) ${percent}%, rgba(255,255,255,0.14) 100%)`,
                }}
              />
              <div className="mt-2 flex justify-between text-[12px] text-white/40">
                <span className="numbers">0 ₸</span>
                <span className="numbers">{formatTenge(SLIDER_MAX)}</span>
              </div>
            </div>

            <div className="border-t border-white/15 pt-6">
              <p className="mb-4 text-[12px] font-bold uppercase tracking-[0.08em] text-white/45">
                {l.aiRecommendationsKeyFactors}
              </p>
              <div className="divide-y divide-white/10">
                {factors.map((f) => (
                  <div
                    key={f.label}
                    className={`grid grid-cols-[28px_minmax(0,1fr)_auto] items-center gap-3 py-3 ${f.strong ? "text-orange" : "text-white/85"}`}
                  >
                    <f.icon size={17} strokeWidth={1.8} className={f.strong ? "text-orange" : "text-white/50"} aria-hidden="true" />
                    <p className="min-w-0 text-[13px] font-medium leading-snug sm:text-[14px]">{f.label}</p>
                    <p className={`numbers text-right text-[13px] font-bold sm:text-[14px] ${f.strong ? "text-orange" : "text-white"}`}>
                      {f.value < 0 ? "−" : ""}
                      {formatTenge(Math.abs(f.value))}
                    </p>
                  </div>
                ))}
              </div>
              <p className="mt-5 max-w-[620px] text-[11.5px] leading-relaxed text-white/45">
                {l.aiRecommendationsIllustrative}
              </p>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
