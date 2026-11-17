"use client";

import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import { useTranslation } from "@/lib/language-context";
import { fadeUp } from "@/lib/animations";

export default function HowItWorks() {
  const { t } = useTranslation();
  const l = t.landing;

  const steps = [
    { num: "01", title: l.step1Title, text: l.step1Text },
    { num: "02", title: l.step2Title, text: l.step2Text },
    { num: "03", title: l.step3Title, text: l.step3Text },
  ];

  return (
    <section id="how-it-works" className="bg-white py-16 sm:py-20 lg:py-24">
      <div className="container-arqau">
        <div className="grid gap-10 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-16">
          <div className="max-w-[520px]">
            <motion.span {...fadeUp(0)} className="pill-badge mb-6">
              {l.howItWorksEyebrow}
            </motion.span>
            <motion.h2
              {...fadeUp(0.08)}
              className="max-w-[11ch] text-[34px] font-extrabold leading-[1.08] tracking-normal text-ink text-balance sm:text-[44px] lg:text-[48px]"
            >
              {l.howItWorksTitle}
            </motion.h2>
            <motion.p
              {...fadeUp(0.16)}
              className="mt-5 max-w-[440px] text-[16px] leading-[1.7] text-ink-soft sm:text-[17px]"
            >
              {l.howItWorksSubtitle}
            </motion.p>
          </div>

          <div>
            <div className="grid gap-0 sm:grid-cols-3 sm:divide-x sm:divide-border">
              {steps.map((s, i) => (
                <motion.div
                  key={s.num}
                  {...fadeUp(0.1 + i * 0.08)}
                  className="grid grid-cols-[40px_1fr] gap-x-4 border-t border-border py-5 sm:block sm:border-t-0 sm:px-5 sm:py-0 first:sm:pl-0 last:sm:pr-0"
                >
                  <span className="numbers row-span-2 font-serif text-[22px] italic leading-none text-orange sm:block">{s.num}</span>
                  <h3 className="text-[17px] font-bold leading-snug text-ink sm:mt-5 sm:text-[18px]">{s.title}</h3>
                  <p className="col-start-2 mt-1 text-[14px] leading-[1.65] text-ink-soft sm:mt-3 sm:text-[15px]">{s.text}</p>
                </motion.div>
              ))}
            </div>

            <motion.a {...fadeUp(0.35)} href="#product" className="btn-outline mt-8 w-fit">
              {l.howItWorksCta} <ArrowRight size={16} className="btn-arrow" />
            </motion.a>
          </div>
        </div>
      </div>
    </section>
  );
}
