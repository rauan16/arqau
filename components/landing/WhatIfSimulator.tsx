"use client";

import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { scenario, evaluateWithdrawal, formatTenge } from "@/lib/demoData";
import { useTranslation } from "@/lib/language-context";

const statusStyles: Record<string, { bg: string; text: string; bar: string }> = {
  comfortable: { bg: "bg-orange-soft", text: "text-orange", bar: "bg-green-bright" },
  caution: { bg: "bg-orange-soft/60", text: "text-orange", bar: "bg-green" },
  "high-risk": { bg: "bg-red-50", text: "text-red-700", bar: "bg-red-500" },
};

const easeOut = [0.22, 1, 0.36, 1] as const;

export default function WhatIfSimulator() {
  const { t } = useTranslation();
  const [amount, setAmount] = useState(50000);
  const result = useMemo(() => evaluateWithdrawal(amount), [amount]);
  const pct = (amount / scenario.available) * 100;
  const styles = statusStyles[result.status];

  return (
    <section id="simulator" className="py-28 lg:py-36 bg-cream">
      <div className="container-arqau">
        <div className="max-w-[600px] mb-16">
          <motion.p
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.5, ease: easeOut }}
            className="eyebrow mb-5 reveal-text"
          >
            Try it yourself
          </motion.p>
          <motion.h2
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.6, ease: easeOut }}
            className="text-[38px] sm:text-[50px] lg:text-[58px] font-extrabold leading-[1.02] tracking-[-0.025em] reveal-text text-balance"
          >
            {t.landing.whatIfTitle}
          </motion.h2>
          <motion.p
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.6, delay: 0.1, ease: easeOut }}
            className="mt-6 text-[18px] leading-[1.7] text-ink-soft reveal-text"
          >
            {t.landing.whatIfSubtitle}
          </motion.p>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.6, ease: easeOut }}
          className="rounded-[30px] border border-ink/[0.08] bg-white p-8 sm:p-11 lg:p-14 max-w-[920px] shadow-[0_30px_70px_-50px_rgba(21,21,21,0.65)]"
        >
          <div className="flex items-baseline justify-between mb-2">
            <p className="text-[13px] text-ink-soft">{t.landing.whatIfWithdrawalAmount}</p>
            <p className="text-[13px] text-ink-soft">{t.whatIf.available}: {formatTenge(scenario.available)}</p>
          </div>

          <motion.p
            key={amount}
            initial={{ opacity: 0.45, y: 8, scale: 0.985 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.22, ease: "easeOut" }}
            className="text-[44px] sm:text-[58px] lg:text-[66px] font-extrabold tracking-[-0.035em] mb-8 origin-left"
          >
            {formatTenge(amount)}
          </motion.p>

          <div>
            <input
              type="range"
              min={0}
              max={scenario.available}
              step={1000}
              value={amount}
              onChange={(e) => setAmount(Number(e.target.value))}
              aria-label="Withdrawal amount"
              className="w-full h-3 rounded-full appearance-none bg-ink/[0.08] accent-green-deep focus-ring mb-3"
              style={{
                background: `linear-gradient(to right, var(--green-deep) ${pct}%, rgba(21,21,21,0.08) ${pct}%)`,
              }}
            />
            <div className="flex justify-between text-[12px] text-ink-soft/60 mb-10">
              <span>0 ₸</span>
              <span>{formatTenge(scenario.available)}</span>
            </div>
          </div>

          <div className="grid sm:grid-cols-3 gap-6 pt-2">
            <motion.div
              key={`remaining-${amount}`}
              initial={{ opacity: 0.5, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.22 }}
            >
              <p className="text-[12px] text-ink-soft mb-1.5">{t.whatIf.remainingBalance}</p>
              <p className="text-[23px] font-bold tracking-tight numbers">{formatTenge(result.remainingAvailable)}</p>
            </motion.div>
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-80px" }}
              transition={{ duration: 0.45, delay: 0.12, ease: easeOut }}
            >
              <p className="text-[12px] text-ink-soft mb-1.5">{t.whatIf.upcomingExpenses}</p>
              <p className="text-[23px] font-bold tracking-tight numbers">{formatTenge(scenario.upcomingExpensesTotal)}</p>
            </motion.div>
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-80px" }}
              transition={{ duration: 0.45, delay: 0.18, ease: easeOut }}
            >
              <p className="text-[12px] text-ink-soft mb-1.5">{t.whatIf.reserveTarget}</p>
              <p className="text-[23px] font-bold tracking-tight">{formatTenge(scenario.reserveTarget)}</p>
            </motion.div>
          </div>

          <motion.div
            key={result.status}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, ease: easeOut }}
            className={`mt-8 rounded-2xl p-5 ${styles.bg}`}
          >
            <p className={`text-[13px] font-semibold mb-1.5 ${styles.text}`}>{result.label}</p>
            <p className="text-[14.5px] text-ink-soft leading-relaxed">{result.note}</p>
          </motion.div>

          <p className="mt-4 text-[11px] text-ink-soft/50">{t.whatIf.illustrative}</p>
        </motion.div>
      </div>
    </section>
  );
}
