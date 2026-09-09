"use client";

import { motion } from "framer-motion";
import { scenario, formatTenge } from "@/lib/demoData";

const inputs = ["Earned income", "Upcoming expenses", "Reserve target"];

const easeOut = [0.22, 1, 0.36, 1] as const;

export default function RecommendationSection() {
  return (
    <section className="py-28 lg:py-36 bg-cream">
      <div className="container-arqau">
        <div className="max-w-[680px] mb-16 lg:mb-20">
          <motion.p
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.5, ease: easeOut }}
            className="eyebrow mb-5 reveal-text"
          >
            The ARQAU difference
          </motion.p>
          <motion.h2
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.6, ease: easeOut }}
            className="text-[38px] sm:text-[50px] lg:text-[60px] font-extrabold leading-[1.02] tracking-[-0.025em] reveal-text text-balance"
          >
            Not just a number. <span className="font-serif italic font-medium text-green-deep">A recommendation.</span>
          </motion.h2>
        </div>

        <div className="grid lg:grid-cols-[1fr_auto_1fr] gap-8 lg:gap-10 items-center mb-20">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {inputs.map((label, i) => (
              <motion.div
                key={label}
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-60px" }}
                transition={{ duration: 0.5, delay: i * 0.1, ease: easeOut }}
                className="card p-6"
              >
                <p className="text-[15px] font-semibold leading-snug reveal-text">{label}</p>
              </motion.div>
            ))}
          </div>

          <div className="hidden lg:flex items-center justify-center text-[28px] text-ink-soft/30">→</div>

          <motion.div
            initial={{ opacity: 0, scale: 0.96 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true, margin: "-60px" }}
            transition={{ duration: 0.6, delay: 0.3, ease: easeOut }}
            className="rounded-[26px] bg-green-deep text-cream p-9 sm:p-10 shadow-[0_28px_55px_-30px_rgba(47,83,56,0.55)]"
          >
            <p className="text-[14px] font-semibold opacity-85 mb-3 reveal-text">Recommended withdrawal</p>
            <p className="text-[52px] sm:text-[60px] font-extrabold tracking-[-0.03em] mb-5 reveal-text">{formatTenge(scenario.recommended)}</p>
            <p className="text-[13px] text-cream/80 mb-4 leading-relaxed reveal-text">
              Keeps your upcoming expenses covered while protecting your reserve target.
            </p>
            <div className="flex justify-between text-[14px] pt-4 border-t border-cream/25 reveal-text">
              <span className="opacity-80">Available</span>
              <span className="font-semibold numbers">{formatTenge(scenario.available)}</span>
            </div>
            <div className="flex justify-between text-[14px] mt-2 reveal-text">
              <span className="opacity-80">Reserve target</span>
              <span className="font-semibold">{formatTenge(scenario.reserveTarget)}</span>
            </div>
            <p className="mt-4 text-[11px] text-cream/50">Illustrative example</p>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
