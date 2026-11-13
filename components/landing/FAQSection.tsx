"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Plus } from "lucide-react";
import { easeOut, fadeUp } from "@/lib/animations";
import { useTranslation } from "@/lib/language-context";

export default function FAQSection() {
  const { t } = useTranslation();
  const l = t.landing;
  const [open, setOpen] = useState<Record<number, boolean>>({});

  const items = [
    { q: l.faq1Question, a: l.faq1Answer },
    { q: l.faq2Question, a: l.faq2Answer },
    { q: l.faq3Question, a: l.faq3Answer },
    { q: l.faq4Question, a: l.faq4Answer },
    { q: l.faq5Question, a: l.faq5Answer },
    { q: l.faq6Question, a: l.faq6Answer },
  ];

  return (
    <section id="faq" className="bg-cream py-16 sm:py-20 lg:py-24">
      <div className="container-arqau">
        <div className="grid gap-10 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-16">
          <div className="max-w-[520px]">
            <motion.span {...fadeUp(0)} className="pill-badge mb-6">
              {l.faqEyebrow}
            </motion.span>
            <motion.h2
              {...fadeUp(0.08)}
              className="max-w-[11ch] text-[34px] font-extrabold leading-[1.08] tracking-normal text-ink text-balance sm:text-[44px] lg:text-[48px]"
            >
              {l.faqTitleLead}
              <span className="font-serif font-medium italic text-orange">{l.faqTitleHighlight}</span>
              {l.faqTitleTail}
            </motion.h2>
          </div>

          <div className="divide-y divide-border border-y border-border">
            {items.map((item, i) => {
              const isOpen = Boolean(open[i]);
              return (
                <motion.div
                  key={item.q}
                  {...fadeUp((i % 2) * 0.06)}
                >
                  <h3>
                    <button
                      type="button"
                      onClick={() => setOpen((prev) => ({ ...prev, [i]: !prev[i] }))}
                      aria-expanded={isOpen}
                      aria-controls={`faq-answer-${i}`}
                      id={`faq-question-${i}`}
                      className="flex w-full items-center justify-between gap-4 py-4 text-left focus-ring sm:py-5"
                    >
                      <span className="text-[15px] font-bold leading-snug text-ink sm:text-[16px]">{item.q}</span>
                      <Plus
                        size={18}
                        className={`shrink-0 text-orange transition-transform duration-300 ${isOpen ? "rotate-45" : ""}`}
                        aria-hidden="true"
                      />
                    </button>
                  </h3>
                  <AnimatePresence initial={false}>
                    {isOpen && (
                      <motion.div
                        id={`faq-answer-${i}`}
                        role="region"
                        aria-labelledby={`faq-question-${i}`}
                        initial={{ opacity: 0, y: -4 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -4 }}
                        transition={{ duration: 0.22, ease: easeOut }}
                        className="overflow-hidden"
                      >
                        <p className="max-w-[620px] pb-5 pr-8 text-[14px] leading-[1.7] text-ink-soft sm:text-[15px]">{item.a}</p>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </motion.div>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}
