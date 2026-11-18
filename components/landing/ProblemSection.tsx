"use client";

import { motion } from "framer-motion";
import { CalendarClock, Clock3, LockKeyhole } from "lucide-react";
import { useTranslation } from "@/lib/language-context";
import { fadeUp } from "@/lib/animations";

const situations = [
  { icon: CalendarClock, key: "problemCard1", number: "01" },
  { icon: Clock3, key: "problemCard2", number: "02" },
  { icon: LockKeyhole, key: "problemCard3", number: "03" },
] as const;

export default function ProblemSection() {
  const { t } = useTranslation();
  const l = t.landing;

  return (
    <section id="problem" className="bg-ink py-16 text-cream sm:py-20 lg:py-24">
      <div className="container-arqau">
        <div className="grid gap-10 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-16">
          <div className="max-w-[520px]">
            <motion.span {...fadeUp(0)} className="pill-badge mb-6 bg-orange/15 text-orange">
              {l.problemEyebrow}
            </motion.span>

            <motion.h2
              {...fadeUp(0.08)}
              className="max-w-[12ch] text-[34px] font-extrabold leading-[1.08] tracking-normal text-white text-balance sm:text-[44px] lg:text-[48px]"
            >
              {l.problemTitleLead}
              <span className="font-serif font-medium italic text-orange">{l.problemTitleHighlight}</span>
              {l.problemTitleTail}
            </motion.h2>

            <motion.p
              {...fadeUp(0.16)}
              className="mt-5 max-w-[460px] text-[16px] leading-[1.7] text-white/65 sm:text-[17px]"
            >
              {l.problemSubtitle}
            </motion.p>
          </div>

          <motion.div {...fadeUp(0.18)} className="divide-y divide-white/15 border-y border-white/15">
            {situations.map((item) => (
              <div key={item.key} className="grid grid-cols-[36px_24px_1fr] items-center gap-3 py-5 sm:gap-5 sm:py-6">
                <span className="numbers font-serif text-[17px] italic text-orange">{item.number}</span>
                <item.icon size={18} strokeWidth={1.7} className="text-white/55" aria-hidden="true" />
                <p className="text-[16px] font-semibold leading-snug text-white sm:text-[18px]">{l[item.key]}</p>
              </div>
            ))}
          </motion.div>
        </div>
      </div>
    </section>
  );
}
