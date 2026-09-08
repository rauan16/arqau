"use client";

import { motion } from "framer-motion";
import { CircleDollarSign, Sparkles, HandCoins, Shuffle, MessageCircle, ShieldCheck } from "lucide-react";

const features = [
  [CircleDollarSign, "Earned wages", "See what you’ve earned so far, in real time."],
  [Sparkles, "Smart recommendations", "Get personalized advice on how much to withdraw."],
  [HandCoins, "Expense planning", "Keep track of your bills and upcoming payments."],
  [Shuffle, "What-if simulator", "Try different scenarios and plan with confidence."],
  [MessageCircle, "AI financial assistant", "Get clear explanations in simple language."],
  [ShieldCheck, "Build your reserve", "Create a safety net for the future."],
];

const easeOut = [0.22, 1, 0.36, 1] as const;

export default function DifferenceSection() {
  return (
    <section id="product" className="py-28 lg:py-36 bg-cream">
      <div className="container-arqau grid lg:grid-cols-[0.85fr_1.5fr] gap-16 lg:gap-24 items-start">
        <div className="lg:sticky lg:top-32">
          <motion.p
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.5, ease: easeOut }}
            className="eyebrow mb-5 uppercase"
          >
            Why ARQAU
          </motion.p>

          <motion.h2
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.6, ease: easeOut }}
            className="text-[36px] sm:text-[46px] lg:text-[52px] font-extrabold leading-[1.03] tracking-[-0.02em] max-w-[460px] text-balance"
          >
            More than
            <br />
            just access.
            <br />
            <span className="font-serif italic font-medium text-orange">It&apos;s a smarter way to manage your money.</span>
          </motion.h2>

          <motion.p
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.6, delay: 0.1, ease: easeOut }}
            className="mt-6 text-[16px] leading-[1.7] text-ink-soft max-w-[400px]"
          >
            ARQAU doesn&apos;t just show you how much you can withdraw. It helps you decide how much to take, based on your upcoming expenses and financial goals.
          </motion.p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-8 gap-y-6">
          {features.map(([Icon, title, copy], index) => (
            <motion.div
              key={`feature-${index}`}
              initial={{ opacity: 0, y: 14 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-80px" }}
              transition={{ duration: 0.5, delay: index * 0.07, ease: easeOut }}
              className="card p-6 min-h-[170px] flex flex-col"
            >
              <div className="w-11 h-11 rounded-full border border-orange/25 bg-cream-orange flex items-center justify-center text-orange mb-4">
                <Icon size={18} strokeWidth={1.7} />
              </div>
              <h3 className="text-[15px] font-semibold mb-1.5 reveal-text">{title as string}</h3>
              <p className="text-[13.5px] leading-[1.6] text-ink-soft reveal-text">{copy as string}</p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
