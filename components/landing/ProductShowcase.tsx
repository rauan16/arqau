"use client";

import { motion } from "framer-motion";
import MiniPhoneFrame from "./MiniPhoneFrame";
import { EarningsScreen, ExpensesScreen, RecommendationScreen, WhatIfScreen, AIScreen } from "./ShowcaseScreens";
import { useTranslation } from "@/lib/language-context";

const screens = [
  { comp: EarningsScreen, label: "Earnings", rotate: -5 },
  { comp: ExpensesScreen, label: "Expenses", rotate: -2.5 },
  { comp: RecommendationScreen, label: "Recommendation", rotate: 0 },
  { comp: WhatIfScreen, label: "What if?", rotate: 2.5 },
  { comp: AIScreen, label: "AI Assistant", rotate: 5 },
];

const easeOut = [0.22, 1, 0.36, 1] as const;

export default function ProductShowcase() {
  const { t } = useTranslation();
  return (
    <section id="features" className="py-28 lg:py-36 bg-cream-orange overflow-hidden">
      <div className="container-arqau grid lg:grid-cols-[0.75fr_1.25fr] gap-16 items-center">
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
            From earnings to expenses, from smart recommendations to AI insights — ARQAU gives you the full picture and helps you make the right decision.
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

        <div className="flex items-center gap-[-30px] pl-4 lg:pl-0 overflow-x-auto lg:overflow-visible pb-6 -mr-4 lg:mr-0 scrollbar-hide">
          {screens.map((s, i) => (
            <motion.div
              key={s.label}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-80px" }}
              transition={{ duration: 0.5, delay: i * 0.08, ease: easeOut }}
              style={{ marginLeft: i === 0 ? 0 : -30, rotate: s.rotate, zIndex: i }}
              className="relative"
            >
              <MiniPhoneFrame>
                <s.comp />
              </MiniPhoneFrame>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
