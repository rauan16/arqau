"use client";

import { useCallback, useMemo, useRef } from "react";
import { motion } from "framer-motion";
import { ArrowLeft, ArrowRight } from "lucide-react";
import {
  AIRecommendationsCard,
  AnalyticsCard,
  EmployeeHomeCard,
  WithdrawalCard,
} from "./ProductCards";
import { useProductDemo } from "./useProductDemo";
import { useTranslation } from "@/lib/language-context";
import { demoCurrentMonthIndex } from "@/lib/demoData";
import type { AnalyticsLabels } from "@/lib/demoData";
import { fadeUp } from "@/lib/animations";

export default function ProductShowcase() {
  const { t } = useTranslation();
  const l = t.landing;
  const trackRef = useRef<HTMLDivElement>(null);

  const labels = useMemo<AnalyticsLabels>(
    () => ({
      weekdays: l.productAnalyticsWeekdays.split(","),
      months: l.productAnalyticsMonthLabels.split(","),
      currentMonthIndex: demoCurrentMonthIndex,
    }),
    [l],
  );

  const demo = useProductDemo(labels);

  const scrollByCard = useCallback((direction: 1 | -1) => {
    const track = trackRef.current;
    if (!track) return;
    const card = track.querySelector<HTMLElement>("[data-product-card]");
    const step = card ? card.offsetWidth + 20 : 350;
    track.scrollBy({ left: direction * step, behavior: "smooth" });
  }, []);

  return (
    <section id="product" className="bg-white py-16 sm:py-20 lg:py-24">
      <div className="container-arqau">
        <div className="flex flex-col gap-8 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-[620px]">
            <motion.span {...fadeUp(0)} className="pill-badge mb-6">
              {l.productEyebrow}
            </motion.span>
            <motion.h2
              {...fadeUp(0.08)}
              className="max-w-[12ch] text-[34px] font-extrabold leading-[1.08] tracking-normal text-ink text-balance sm:text-[44px] lg:text-[48px]"
            >
              {l.productTitleLead}
              <span className="font-serif font-medium italic text-orange">{l.productTitleHighlight}</span>
              {l.productTitleTail}
            </motion.h2>
            <motion.p
              {...fadeUp(0.16)}
              className="mt-5 max-w-[520px] text-[16px] leading-[1.7] text-ink-soft sm:text-[17px]"
            >
              {l.productSubtitle}
            </motion.p>
            <p className="mt-3 text-[12px] leading-relaxed text-ink-muted">{l.productDemoLabel}</p>
          </div>

          <motion.div {...fadeUp(0.2)} className="flex shrink-0 gap-2">
            <button
              type="button"
              onClick={() => scrollByCard(-1)}
              aria-label={l.productPrev}
              className="flex h-11 w-11 items-center justify-center rounded-full border border-border bg-white text-ink transition-colors hover:border-ink focus-ring"
            >
              <ArrowLeft size={17} />
            </button>
            <button
              type="button"
              onClick={() => scrollByCard(1)}
              aria-label={l.productNext}
              className="flex h-11 w-11 items-center justify-center rounded-full border border-border bg-white text-ink transition-colors hover:border-ink focus-ring"
            >
              <ArrowRight size={17} />
            </button>
          </motion.div>
        </div>

        <motion.div
          {...fadeUp(0.28)}
          ref={trackRef}
          tabIndex={0}
          role="region"
          aria-label={l.productTitle}
          className="scrollbar-hide -mr-6 mt-10 flex snap-x snap-mandatory gap-4 overflow-x-auto pr-6 pb-4 focus-ring sm:mt-12 sm:gap-5 lg:mt-14"
        >
          <div data-product-card>
            <EmployeeHomeCard l={l} />
          </div>
          <div data-product-card>
            <AnalyticsCard l={l} demo={demo} />
          </div>
          <div data-product-card>
            <WithdrawalCard l={l} demo={demo} />
          </div>
          <div data-product-card>
            <AIRecommendationsCard l={l} demo={demo} />
          </div>
        </motion.div>
      </div>
    </section>
  );
}
