"use client";

import Image from "next/image";
import { ArrowRight, ArrowUpRight, ChartColumnIncreasing, Sparkles, Target } from "lucide-react";
import HeroInsightCard from "./HeroInsightCard";
import { scenario, formatTenge } from "@/lib/demoData";
import { useTranslation } from "@/lib/language-context";

function CardIcon({ children }: { children: React.ReactNode }) {
  return (
    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-orange-soft text-orange">
      {children}
    </span>
  );
}

export default function Hero() {
  const { t } = useTranslation();
  const h = t.landingHero;

  return (
    <section
      id="top"
      className="relative overflow-hidden bg-cream pb-14 pt-[84px] xl:min-h-[800px] xl:pb-16"
    >
      <div className="absolute inset-0" aria-hidden="true">
        <Image
          src="/hero-warm-workspace.jpg"
          alt=""
          fill
          priority
          sizes="100vw"
          className="object-cover object-[42%_58%] lg:object-center"
        />
        <div
          className="absolute inset-0 bg-[linear-gradient(180deg,rgba(247,244,240,0.96)_0%,rgba(247,244,240,0.9)_26%,rgba(247,244,240,0.45)_52%,rgba(247,244,240,0.12)_68%,rgba(247,244,240,0.82)_100%)] lg:bg-[linear-gradient(100deg,rgba(247,244,240,0.94)_0%,rgba(247,244,240,0.78)_24%,rgba(247,244,240,0.3)_46%,rgba(247,244,240,0.08)_62%,rgba(247,244,240,0.14)_82%,rgba(247,244,240,0.4)_100%)]"
        />
        <div
          className="absolute inset-x-0 bottom-0 h-40 bg-[linear-gradient(180deg,rgba(247,244,240,0)_0%,rgba(247,244,240,0.55)_100%)]"
        />
      </div>

      <div className="relative z-10 mx-auto w-full max-w-[1400px] px-[5%]">
        <div className="grid items-center gap-10 lg:grid-cols-[1.05fr_1fr] lg:gap-8">
          <div className="max-w-[640px] py-2 lg:max-w-[560px] xl:max-w-[640px] xl:py-[72px]">
            <p
              className="reveal-up flex items-center gap-3 text-[11px] font-bold uppercase tracking-[0.22em] text-ink-soft xl:text-[12px]"
              style={{ animationDelay: "0.05s" }}
            >
              <span className="h-[1.5px] w-7 shrink-0 bg-orange" aria-hidden="true" />
              {h.badge}
            </p>

            <h1
              className="reveal-up mt-5 text-[clamp(2.5rem,5.6vw,5.2rem)] font-extrabold leading-[1.02] tracking-[-0.045em] text-ink"
              style={{ animationDelay: "0.13s" }}
            >
              <span className="block">{h.titleLead}</span>
              <span className="block">{h.titleTail}</span>
              <span className="block font-serif text-[0.94em] text-orange italic tracking-[-0.02em]">
                {h.titleHighlight}
              </span>
            </h1>

            <p
              className="reveal-up mt-6 max-w-[480px] text-[1.02rem] leading-[1.65] text-ink-soft md:text-[1.1rem]"
              style={{ animationDelay: "0.23s" }}
            >
              {h.subtitle}
            </p>

            <div
              className="reveal-up mt-8 flex flex-wrap items-center gap-x-7 gap-y-4"
              style={{ animationDelay: "0.33s" }}
            >
              <a href="/signup" className="btn-primary focus-ring">
                {h.ctaPrimary} <ArrowRight size={17} className="btn-arrow" aria-hidden="true" />
              </a>
              <a
                href="/business/register"
                className="group inline-flex items-center gap-2 text-[15.5px] font-bold text-ink underline decoration-orange decoration-2 underline-offset-[6px] transition-colors hover:text-orange-dark focus-ring"
              >
                {h.ctaSecondary}
                <ArrowUpRight
                  size={16}
                  className="text-orange transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5"
                  aria-hidden="true"
                />
              </a>
            </div>

            <p
              className="reveal-up mt-9 text-[0.86rem] font-medium leading-relaxed text-ink-soft xl:mt-10 xl:text-[0.92rem]"
              style={{ animationDelay: "0.41s" }}
            >
              {h.closingLine}
            </p>
          </div>

          <div className="relative mx-auto grid w-full max-w-[600px] gap-4 lg:min-h-[600px] xl:mx-0 xl:max-w-none">
            <div className="pointer-events-none absolute inset-0 hidden lg:block" aria-hidden="true">
              <svg
                className="h-full w-full"
                viewBox="0 0 100 100"
                preserveAspectRatio="none"
                aria-hidden="true"
              >
                <path
                  d="M50 18 C53 18 52 35 55 35"
                  fill="none"
                  stroke="#F26722"
                  strokeWidth={1.5}
                  strokeLinecap="round"
                  strokeOpacity={0.55}
                  vectorEffect="non-scaling-stroke"
                />
                <path
                  d="M60 47 C57 51 56 51 54 55"
                  fill="none"
                  stroke="#F26722"
                  strokeWidth={1.5}
                  strokeLinecap="round"
                  strokeOpacity={0.55}
                  vectorEffect="non-scaling-stroke"
                />
                <path
                  d="M14 68 C10 69 7 72 4 75"
                  fill="none"
                  stroke="#F26722"
                  strokeWidth={1.5}
                  strokeLinecap="round"
                  strokeOpacity={0.55}
                  vectorEffect="non-scaling-stroke"
                />
              </svg>
              <span className="absolute h-[7px] w-[7px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-orange ring-2 ring-white/90" style={{ left: "50%", top: "18%" }} />
              <span className="absolute h-[7px] w-[7px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-orange ring-2 ring-white/90" style={{ left: "55%", top: "35%" }} />
              <span className="absolute h-[7px] w-[7px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-orange ring-2 ring-white/90" style={{ left: "54%", top: "55%" }} />
              <span className="absolute h-[7px] w-[7px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-orange ring-2 ring-white/90" style={{ left: "3.5%", top: "75.5%" }} />
            </div>

            <div
              className="reveal-up order-1 lg:absolute lg:left-[6%] lg:top-[4%] lg:w-[190px] xl:left-[8%] xl:w-[250px]"
              style={{ animationDelay: "0.3s" }}
            >
              <div className="hero-float" style={{ animationDelay: "0.9s" }}>
                <HeroInsightCard>
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2.5">
                      <CardIcon>
                        <Sparkles size={15} aria-hidden="true" />
                      </CardIcon>
                      <span className="text-[9px] font-extrabold uppercase leading-[1.35] tracking-[0.14em] text-orange-dark xl:text-[10px]">
                        {h.cardOneLabel}
                      </span>
                    </div>
                    <ArrowRight size={15} className="shrink-0 text-ink-soft" aria-hidden="true" />
                  </div>

                  <p className="mt-3.5 text-[0.85rem] font-bold leading-[1.45] text-ink">
                    {h.cardOneDescription}
                  </p>
                </HeroInsightCard>
              </div>
            </div>

            <div
              className="reveal-up order-2 lg:absolute lg:left-[50%] lg:top-[20%] lg:w-[190px] xl:left-[55%] xl:w-[222px]"
              style={{ animationDelay: "0.45s" }}
            >
              <div className="hero-float" style={{ animationDelay: "1.8s" }}>
                <HeroInsightCard>
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2.5">
                      <CardIcon>
                        <ChartColumnIncreasing size={15} aria-hidden="true" />
                      </CardIcon>
                      <span className="text-[9px] font-extrabold uppercase leading-[1.35] tracking-[0.14em] text-orange-dark xl:text-[10px]">
                        {h.cardTwoLabel}
                      </span>
                    </div>
                    <span className="shrink-0 text-[9px] font-bold uppercase tracking-[0.12em] text-ink-soft">
                      {h.cardTwoMeta}
                    </span>
                  </div>

                  <p className="numbers mt-3.5 text-[1.75rem] font-extrabold leading-none tracking-[-0.04em] text-ink xl:text-[1.9rem]">
                    {formatTenge(scenario.earned)}
                  </p>

                  <svg
                    className="mt-3.5 h-9 w-full"
                    viewBox="0 0 200 40"
                    fill="none"
                    preserveAspectRatio="none"
                    aria-hidden="true"
                  >
                    <path
                      d="M2 31 C 22 29, 38 24, 56 25 S 96 13, 122 15 S 166 7, 198 9"
                      stroke="#F26722"
                      strokeWidth={2}
                      strokeLinecap="round"
                      vectorEffect="non-scaling-stroke"
                    />
                    <circle cx={196} cy={9} r={3} fill="#F26722" />
                  </svg>
                </HeroInsightCard>
              </div>
            </div>

            <div
              className="reveal-up order-3 lg:absolute lg:left-[12%] lg:top-[54%] lg:w-[205px] xl:left-[14%] xl:w-[240px]"
              style={{ animationDelay: "0.6s" }}
            >
              <div className="hero-float" style={{ animationDelay: "3.1s" }}>
                <HeroInsightCard>
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2.5">
                      <CardIcon>
                        <Target size={15} aria-hidden="true" />
                      </CardIcon>
                      <span className="text-[9px] font-extrabold uppercase leading-[1.35] tracking-[0.14em] text-orange-dark xl:text-[10px]">
                        {h.cardThreeLabel}
                      </span>
                    </div>
                    <ArrowRight size={15} className="shrink-0 text-orange" aria-hidden="true" />
                  </div>

                  <div className="mt-3.5 flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
                    <p className="numbers text-[1.75rem] font-extrabold leading-none tracking-[-0.04em] text-ink xl:text-[1.9rem]">
                      {formatTenge(scenario.recommended)}
                    </p>
                    <span className="text-[9px] font-bold uppercase tracking-[0.12em] text-ink-soft">
                      {h.cardThreeMeta}
                    </span>
                  </div>
                </HeroInsightCard>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
