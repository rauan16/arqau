"use client";

import { motion, useReducedMotion } from "framer-motion";
import { ArrowUpRight, Briefcase, Compass, Wallet } from "lucide-react";
import { fadeUp } from "@/lib/animations";
import { useTranslation } from "@/lib/language-context";

const cardBaseClass =
  "group relative flex flex-col overflow-hidden rounded-[16px] border border-ink/[0.07] bg-white/55 p-7 transition-[transform,border-color,background-color,box-shadow] duration-300 ease-out hover:-translate-y-0.5 hover:border-orange/30 hover:bg-white/80 hover:shadow-[0_18px_36px_-24px_rgba(22,20,18,0.25)] sm:p-8";

// On tablet the third card spans the two-column grid and stays centered; on desktop all three are equal columns.
const cardWideClass = "sm:col-span-2 sm:mx-auto sm:w-full sm:max-w-[520px] lg:col-span-1 lg:max-w-none";

export default function AboutSection() {
  const { t } = useTranslation();
  const l = t.landing;
  const reduceMotion = useReducedMotion();

  const benefits = [
    { icon: Wallet, title: l.aboutBenefit1Title, text: l.aboutBenefit1Text },
    { icon: Briefcase, title: l.aboutBenefit2Title, text: l.aboutBenefit2Text },
    { icon: Compass, title: l.aboutBenefit3Title, text: l.aboutBenefit3Text },
  ];

  // With reduced motion the section renders fully visible, without any entrance animation.
  const rise = (delay = 0) => fadeUp(delay, { reduceMotion: Boolean(reduceMotion) });

  return (
    <section id="about" className="bg-cream py-20 sm:py-24 lg:py-28">
      <div className="container-arqau">
        <div className="mx-auto flex max-w-[900px] flex-col items-center text-center">
          <motion.p {...rise(0)} className="eyebrow flex items-center gap-3 text-[12px]">
            <span className="h-[1.5px] w-7 shrink-0 bg-orange" aria-hidden="true" />
            {l.aboutEyebrow}
          </motion.p>

          <motion.h2
            {...rise(0.08)}
            className="mt-5 text-balance text-[clamp(2.2rem,5.4vw,4.25rem)] font-extrabold leading-[1.06] tracking-[-0.03em] text-ink"
          >
            <span className="block">{l.aboutTitleLead}</span>
            <span className="block font-serif font-medium italic tracking-[-0.02em] text-orange">
              {l.aboutTitleHighlight}
            </span>
          </motion.h2>

          <motion.p
            {...rise(0.16)}
            className="mt-6 max-w-[720px] text-[16px] leading-[1.75] text-ink-soft sm:text-[17px]"
          >
            {l.aboutSubtitle}
          </motion.p>
        </div>

        <ul className="mt-14 grid gap-5 sm:mt-16 sm:grid-cols-2 lg:grid-cols-3 lg:gap-6">
          {benefits.map((benefit, index) => (
            <motion.li
              key={benefit.title}
              {...rise(0.24 + index * 0.1)}
              className={`${cardBaseClass}${index === 2 ? ` ${cardWideClass}` : ""}`}
            >
              <span className="absolute inset-x-7 top-0 h-px bg-orange/35 sm:inset-x-8" aria-hidden="true" />
              <span className="flex h-11 w-11 items-center justify-center rounded-[12px] bg-orange-soft text-orange transition-colors duration-300 group-hover:bg-orange group-hover:text-white">
                <benefit.icon size={20} strokeWidth={1.7} aria-hidden="true" />
              </span>
              <h3 className="mt-6 text-[17px] font-bold leading-snug tracking-[-0.01em] text-ink sm:text-[18px]">
                {benefit.title}
              </h3>
              <p className="mt-2.5 text-[14.5px] leading-[1.7] text-ink-soft">{benefit.text}</p>
            </motion.li>
          ))}
        </ul>

        <motion.div {...rise(0.56)} className="mt-12 flex justify-center sm:mt-14">
          <a
            href="/business/register"
            className="group inline-flex items-center gap-2 text-[15.5px] font-bold text-ink underline decoration-orange decoration-2 underline-offset-[6px] transition-colors hover:text-orange-dark focus-ring"
          >
            {l.aboutCta}
            <ArrowUpRight
              size={16}
              className="text-orange transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
              aria-hidden="true"
            />
          </a>
        </motion.div>
      </div>
    </section>
  );
}
