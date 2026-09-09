"use client";

import { motion } from "framer-motion";
import { Briefcase, Wallet, Receipt, ScanSearch, BadgeCheck } from "lucide-react";

const stages = [
  { icon: Briefcase, title: "Your work", text: "Every shift and workday builds toward your salary." },
  { icon: Wallet, title: "Earned income", text: "ARQAU tracks what you've already earned, in real time." },
  { icon: Receipt, title: "Upcoming expenses", text: "Rent, food, transport — the costs already on their way." },
  { icon: ScanSearch, title: "ARQAU analysis", text: "Earnings, expenses and your reserve, considered together." },
  { icon: BadgeCheck, title: "Recommended withdrawal", text: "One clear number that keeps you covered." },
];

const easeOut = [0.22, 1, 0.36, 1] as const;

export default function HowItWorks() {
  return (
    <section id="how-it-works" className="py-28 lg:py-36 bg-cream">
      <div className="container-arqau">
        <div className="max-w-[680px] mb-16 lg:mb-24">
          <motion.p
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.5, ease: easeOut }}
            className="eyebrow mb-5 reveal-text"
          >
            How ARQAU works
          </motion.p>
          <motion.h2
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.6, ease: easeOut }}
            className="text-[38px] sm:text-[48px] lg:text-[54px] font-extrabold leading-[1.04] tracking-[-0.02em] reveal-text text-balance"
          >
            From earned income to a smarter decision.
          </motion.h2>
          <motion.p
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.6, delay: 0.1, ease: easeOut }}
            className="mt-6 text-[18px] leading-[1.7] text-ink-soft reveal-text max-w-[560px]"
          >
            Work becomes earned income. Earned income becomes a clear, controlled decision.
          </motion.p>
        </div>

        <div className="relative">
          <div className="hidden lg:block absolute top-[26px] left-0 right-0 h-px bg-ink/[0.08]" />
          <motion.div
            initial={{ scaleX: 0 }}
            whileInView={{ scaleX: 1 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 1.1, ease: easeOut }}
            style={{ transformOrigin: "left" }}
            className="hidden lg:block absolute top-[26px] left-0 right-0 h-px bg-green-deep"
          />

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-10 lg:gap-6">
            {stages.map((s, i) => (
              <motion.div
                key={s.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-60px" }}
                transition={{ duration: 0.5, delay: i * 0.1, ease: easeOut }}
                className="relative"
              >
                <div className="relative z-10 w-[58px] h-[58px] rounded-full bg-cream border border-ink/[0.1] flex items-center justify-center mb-5">
                  <s.icon size={20} className="text-green-deep" strokeWidth={1.75} />
                </div>
                <p className="text-[11px] font-bold tracking-[0.12em] text-green-deep mb-3">0{i + 1}</p>
                <h3 className="text-[18px] font-bold mb-2 reveal-text">{s.title}</h3>
                <p className="text-[15px] leading-[1.7] text-ink-soft max-w-[240px] reveal-text">{s.text}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
