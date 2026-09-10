"use client";

import { motion } from "framer-motion";
import MiniPhoneFrame from "./MiniPhoneFrame";
import { EarningsScreen, ExpensesScreen, RecommendationScreen, WhatIfScreen, AIScreen } from "./ShowcaseScreens";
import { useTranslation } from "@/lib/language-context";

const easeOut = [0.22, 1, 0.36, 1] as const;

export default function ProductShowcase() {
  const { t } = useTranslation();
  const screens = [
    { comp: EarningsScreen, label: t.landing.earningsTitle || "Earnings", rotate: -5 },
    { comp: ExpensesScreen, label: t.landing.expensesTitle || "Expenses", rotate: -2.5 },
    { comp: RecommendationScreen, label: t.landing.recommendationTitle || "Recommendation", rotate: 0 },
    { comp: WhatIfScreen, label: t.whatIf.title || "What if?", rotate: 2.5 },
    { comp: AIScreen, label: t.ai.title || "AI Assistant", rotate: 5 },
  ];
  return (
    <section id="features" className="py-28 lg:py-36 bg-cream-orange overflow-hidden">
      <div className="container-arqau grid lg:grid-cols-[0.75fr_1.25fr] gap-16 items-center min-w-0">
        <div className="max-w-[440px]">
          <motion.p
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.5, ease: easeOut }}
            className="eyebrow mb-5 reveal-text"
          >
            Everything you need
          </motion.p>
          <motion.h2
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.6, ease: easeOut }}
            className="text-[36px] sm:text-[46px] lg:text-[52px] font-serif font-medium leading-[1.04] tracking-[-0.02em] mb-6 reveal-text text-balance"
          >
            Your financial life,
            <br />
            all in one place.
          </motion.h2>
          <motion.p
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.6, delay: 0.1, ease: easeOut }}
            className="text-[18px] leading-[1.7] text-ink-soft mb-9 max-w-[460px] reveal-text"
          >
            {t.landing.productShowcaseCopy}
          </motion.p>
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.6, delay: 0.2, ease: easeOut }}
          >
            <a href="#simulator" className="btn-primary">
              Explore all features <span className="btn-arrow">→</span>
            </a>
          </motion.div>
        </div>

        <div className="flex gap-3 overflow-x-auto lg:gap-[-30px] lg:overflow-visible pb-6 px-4 lg:px-0 scrollbar-hide w-full max-w-full min-w-0">
          {screens.map((s, i) => (
            <motion.div
              key={s.label}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-80px" }}
              transition={{ duration: 0.5, delay: i * 0.08, ease: easeOut }}
              style={{ rotate: s.rotate, zIndex: i }}
              className="relative shrink-0"
            >
              <div className="sm:hidden">
                <div className="w-[108px] h-[216px] shrink-0 rounded-[20px] bg-near-black p-[3px] shadow-[0_18px_36px_-10px_rgba(20,15,10,0.4)]">
                  <div className="relative w-full h-full rounded-[14px] overflow-hidden bg-cream border border-black/40">
                    <div className="absolute top-[3px] left-1/2 -translate-x-1/2 w-[28px] h-[7px] bg-near-black rounded-full z-20" />
                    <s.comp />
                  </div>
                </div>
              </div>
              <div className="hidden sm:block">
                <MiniPhoneFrame>
                  <s.comp />
                </MiniPhoneFrame>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}