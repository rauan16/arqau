"use client";

import { motion } from "framer-motion";
import { ArrowRight, BarChart3, Check } from "lucide-react";
import { useTranslation } from "@/lib/language-context";
import { easeOut, fadeUp } from "@/lib/animations";

export default function PricingSection() {
  const { t } = useTranslation();
  const l = t.landing;

  const plans = [
    {
      key: "start",
      title: l.pricingStartTitle,
      desc: l.pricingStartDesc,
      price: l.pricingStartPrice,
      features: [l.pricingStartFeature1, l.pricingStartFeature2, l.pricingStartFeature3],
      cta: l.pricingStartCta,
      href: "/signup",
      dark: false,
    },
    {
      key: "business",
      title: l.pricingBusinessTitle,
      desc: l.pricingBusinessDesc,
      price: l.pricingBusinessPrice,
      features: [
        l.pricingBusinessFeature1,
        l.pricingBusinessFeature2,
        l.pricingBusinessFeature3,
        l.pricingBusinessFeature4,
      ],
      cta: l.pricingBusinessCta,
      href: "/business/register",
      dark: true,
    },
  ];

  return (
    <section id="pricing" className="bg-cream py-16 sm:py-20 lg:py-24">
      <div className="container-arqau">
        <div className="grid items-start gap-10 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-16">
          <div className="max-w-[520px] lg:pt-3">
            <motion.span {...fadeUp(0)} className="pill-badge mb-6">
              {l.pricingEyebrow}
            </motion.span>
            <motion.h2
              {...fadeUp(0.08)}
              className="max-w-[12ch] text-[34px] font-extrabold leading-[1.08] tracking-normal text-ink text-balance sm:text-[44px] lg:text-[48px]"
            >
              {l.pricingTitleLead}
              <span className="font-serif font-medium italic text-orange">{l.pricingTitleHighlight}</span>
              {l.pricingTitleTail}
            </motion.h2>
            <motion.p
              {...fadeUp(0.16)}
              className="mt-5 max-w-[440px] text-[16px] leading-[1.7] text-ink-soft sm:text-[17px]"
            >
              {l.pricingSubtitle}
            </motion.p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2 sm:gap-0 sm:divide-x sm:divide-border">
            {plans.map((p, i) => (
              <motion.div
                key={p.key}
                initial={{ opacity: 0, y: 28 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-80px" }}
                transition={{ duration: 0.7, delay: 0.1 + i * 0.1, ease: easeOut }}
                className={`flex h-full flex-col rounded-[12px] p-6 sm:rounded-none sm:px-6 sm:py-7 lg:px-8 ${
                  p.dark
                    ? "bg-ink text-white sm:rounded-r-[12px]"
                    : "border border-border bg-white text-ink sm:border-y sm:border-l sm:border-r-0 sm:rounded-l-[12px]"
                }`}
              >
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="text-[20px] font-extrabold">{p.title}</h3>
                    <p className={`mt-1 text-[13.5px] ${p.dark ? "text-white/50" : "text-ink-soft"}`}>{p.desc}</p>
                  </div>
                  {p.dark && (
                    <span className="flex h-11 w-11 items-center justify-center rounded-[13px] bg-white/[0.08] text-orange">
                      <BarChart3 size={19} strokeWidth={2} />
                    </span>
                  )}
                </div>

                <div className="mt-6 flex flex-wrap items-baseline gap-x-2 gap-y-1">
                  <span className="numbers text-[36px] font-extrabold leading-none">{p.price}</span>
                  <span className={`text-[14px] font-semibold ${p.dark ? "text-white/50" : "text-ink-soft"}`}>
                    {l.pricingPeriod}
                  </span>
                </div>
                <p className={`mt-1.5 text-[13px] ${p.dark ? "text-white/40" : "text-ink-muted"}`}>
                  {l.pricingPeriodPerEmployee}
                </p>

                <ul className="mt-6 space-y-3">
                  {p.features.map((f) => (
                    <li key={f} className="flex items-start gap-3">
                      <Check
                        size={16}
                        strokeWidth={3}
                        className={`mt-0.5 shrink-0 ${p.dark ? "text-orange" : "text-orange"}`}
                      />
                      <span className={`text-[14.5px] leading-snug ${p.dark ? "text-white/80" : "text-ink-soft"}`}>{f}</span>
                    </li>
                  ))}
                </ul>

                <a
                  href={p.href}
                  className={`mt-7 flex w-full items-center justify-center gap-2 rounded-full py-3 text-[14px] font-bold transition-colors ${
                    p.dark
                      ? "bg-white text-ink hover:bg-orange-soft"
                      : "bg-orange text-white hover:bg-orange-dark"
                  }`}
                >
                  {p.cta} <ArrowRight size={16} />
                </a>
              </motion.div>
            ))}
          </div>
        </div>

        <motion.p
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="mt-6 max-w-[760px] text-[12.5px] leading-relaxed text-ink-muted lg:mt-8"
        >
          {l.pricingIllustrative}
        </motion.p>
      </div>
    </section>
  );
}
