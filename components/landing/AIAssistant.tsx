"use client";

import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";
import { useTranslation } from "@/lib/language-context";

const messages = [
  { from: "user", text: "What happens if I withdraw 80,000 ₸?" },
  { from: "arqau", text: "You can withdraw 80,000 ₸, but that would reduce your reserve below the recommended level." },
  { from: "user", text: "What amount would be safer?" },
  { from: "arqau", text: "50,000 ₸ would leave enough to cover your upcoming expenses while maintaining your reserve." },
];

const easeOut = [0.22, 1, 0.36, 1] as const;

export default function AIAssistant() {
  const { t } = useTranslation();
  return (
    <section id="ai-assistant" className="py-32 lg:py-40 bg-near-black text-cream">
      <div className="container-arqau grid lg:grid-cols-[0.8fr_1.2fr] gap-16 lg:gap-24 items-center">
        <div className="max-w-[440px]">
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.5, ease: easeOut }}
            className="flex items-center gap-2 mb-5"
          >
            <Sparkles size={16} className="text-green-bright" />
            <p className="text-[14px] font-semibold tracking-wide text-green-bright reveal-text">{t.landing.aiEyebrow}</p>
          </motion.div>
          <motion.h2
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.6, ease: easeOut }}
            className="text-[38px] sm:text-[50px] lg:text-[58px] font-extrabold leading-[1.01] tracking-[-0.03em] mb-7 reveal-text text-balance"
          >
            Ask your money anything.
          </motion.h2>
          <motion.p
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.6, delay: 0.1, ease: easeOut }}
            className="text-[18px] leading-[1.7] text-cream/65 mb-7 max-w-[450px] reveal-text"
          >
            {t.landing.aiSubtitle}
          </motion.p>
          <motion.p
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: "-100px" }}
            transition={{ duration: 0.6, delay: 0.2, ease: easeOut }}
            className="text-[12.5px] text-cream/40 leading-relaxed max-w-[380px]"
          >
            {t.landing.aiDisclaimer}
          </motion.p>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.6, ease: easeOut }}
          className="rounded-[30px] bg-white/[0.05] border border-white/10 p-7 sm:p-10 max-w-[620px] shadow-[0_30px_80px_-50px_rgba(0,0,0,0.8)]"
        >
          <div className="flex items-center justify-between mb-7 pb-5 border-b border-white/10">
            <div>
              <p className="text-[11px] tracking-[0.12em] uppercase text-cream/45">Context-aware guidance</p>
              <p className="text-[15px] font-semibold mt-1">Your ARQAU conversation</p>
            </div>
            <Sparkles size={18} className="text-green-bright" />
          </div>
          <div className="space-y-5">
            {messages.map((m, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 12 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-40px" }}
                transition={{ duration: 0.4, delay: i * 0.15, ease: easeOut }}
                className={`max-w-[84%] rounded-2xl px-5 py-4 text-[15px] leading-[1.6] ${
                  m.from === "user"
                    ? "ml-auto bg-orange text-cream rounded-tr-sm"
                    : "mr-auto bg-white/[0.06] text-cream/90 rounded-tl-sm"
                }`}
              >
                {m.text}
              </motion.div>
            ))}
          </div>
          <p className="mt-5 text-[11px] text-cream/35">
            {t.landing.aiIllustrative}
          </p>
        </motion.div>
      </div>
    </section>
  );
}
