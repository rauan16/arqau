"use client";

import { motion } from "framer-motion";
import { ArrowRight, Award, Handshake, Plug, UserRoundCheck, Users } from "lucide-react";
import { useTranslation } from "@/lib/language-context";
import { easeOut, fadeUp } from "@/lib/animations";

const benefits = [
  { icon: UserRoundCheck, titleKey: "employerCard1Title", textKey: "employerCard1Text" },
  { icon: Award, titleKey: "employerCard2Title", textKey: "employerCard2Text" },
  { icon: Plug, titleKey: "employerCard3Title", textKey: "employerCard3Text" },
  { icon: Handshake, titleKey: "employerCard4Title", textKey: "employerCard4Text" },
  { icon: Users, titleKey: "employerCard5Title", textKey: "employerCard5Text" },
] as const;

export default function EmployerSection() {
  const { t } = useTranslation();
  const l = t.landing;

  return (
    <section id="solutions" className="relative overflow-hidden bg-cream py-16 sm:py-20 lg:py-28">
      {/* Soft warm wash behind the hero and a thin hairline accent at the section edge. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-[380px]"
        style={{
          background: "radial-gradient(58% 100% at 50% 0%, var(--cream-orange) 0%, transparent 72%)",
          opacity: 0.8,
        }}
      />
      <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 top-0 h-px bg-border" />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute left-1/2 top-0 h-[2px] w-16 -translate-x-1/2 bg-orange/50"
      />

      <div className="container-arqau relative">
        <div className="mx-auto flex max-w-[780px] flex-col items-center text-center">
          <motion.span {...fadeUp(0)} className="pill-badge mb-5">
            {l.employerEyebrow}
          </motion.span>

          <motion.p {...fadeUp(0.05)} className="eyebrow">
            {l.employerCorporateLabel}
          </motion.p>

          <motion.h2
            {...fadeUp(0.1)}
            className="mt-4 text-balance text-[34px] font-extrabold leading-[1.06] tracking-normal text-ink sm:text-[46px] lg:text-[54px]"
          >
            {l.employerTitleLead}{" "}
            <span className="font-serif font-medium italic text-orange">{l.employerTitleHighlight}</span>
            {l.employerTitleTail}
          </motion.h2>

          <motion.p
            {...fadeUp(0.18)}
            className="mt-6 max-w-[620px] text-[16px] leading-[1.75] text-ink-soft sm:text-[17px]"
          >
            {l.employerSubtitle}
          </motion.p>

          <motion.div
            {...fadeUp(0.26)}
            className="mt-9 flex w-full flex-col items-stretch gap-3 sm:w-auto sm:flex-row sm:items-center sm:gap-4"
          >
            <a href="/business/register" className="btn-primary w-full sm:w-auto">
              {l.employerCta} <ArrowRight size={17} className="btn-arrow" />
            </a>
            <a href="#product" className="btn-outline w-full sm:w-auto">
              {l.employerCtaSecondary} <ArrowRight size={16} className="btn-arrow" />
            </a>
          </motion.div>
        </div>

        <div className="mt-14 grid gap-4 sm:mt-16 sm:grid-cols-2 sm:gap-5 lg:grid-cols-3 xl:grid-cols-5">
          {benefits.map((b, index) => (
            <motion.article
              key={b.titleKey}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-60px" }}
              transition={{ duration: 0.6, delay: 0.05 + index * 0.07, ease: easeOut }}
              className="group flex flex-col rounded-[16px] border border-border bg-white/75 p-6 transition-colors duration-300 hover:border-orange/40 hover:bg-white"
            >
              <b.icon size={22} strokeWidth={1.7} className="text-orange" aria-hidden="true" />
              <h3 className="mt-4 text-[15.5px] font-extrabold leading-snug text-ink">{l[b.titleKey]}</h3>
              <p className="mt-2 text-[13.5px] leading-[1.65] text-ink-soft">{l[b.textKey]}</p>
              <span
                aria-hidden="true"
                className="mt-5 h-[2px] w-6 rounded-full bg-orange/30 transition-all duration-300 group-hover:w-12 group-hover:bg-orange"
              />
            </motion.article>
          ))}
        </div>

        <motion.p
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.2 }}
          className="mx-auto mt-10 max-w-[720px] text-center text-[12.5px] leading-relaxed text-ink-muted lg:mt-12"
        >
          {l.employerDisclaimer}
        </motion.p>
      </div>
    </section>
  );
}
