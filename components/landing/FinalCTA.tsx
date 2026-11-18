"use client";

import { motion } from "framer-motion";
import { ArrowRight } from "lucide-react";
import Image from "next/image";
import { useTranslation } from "@/lib/language-context";
import { easeOut } from "@/lib/animations";

export default function FinalCTA() {
  const { t } = useTranslation();
  const l = t.landing;

  return (
    <section id="final-cta" className="bg-cream py-8 sm:py-12 lg:py-16">
      <div className="container-arqau">
        <motion.div
          initial={{ opacity: 0, y: 28 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.8, ease: easeOut }}
          className="relative min-h-[480px] overflow-hidden rounded-[16px] lg:min-h-[440px]"
        >
          <Image
            src="/Kazakhstan1-e1496914203779.jpg"
            alt={l.finalCTAImageAlt}
            fill
            sizes="(max-width: 1280px) 100vw, 1280px"
            className="object-cover object-[50%_45%]"
          />
          <div
            aria-hidden="true"
            className="absolute inset-0"
            style={{
              background:
                "linear-gradient(100deg, rgba(20,14,10,0.90) 0%, rgba(20,14,10,0.72) 48%, rgba(20,14,10,0.18) 100%)",
            }}
          />

          <div className="relative z-10 flex min-h-[480px] flex-col justify-center px-6 py-12 sm:px-10 lg:min-h-[440px] lg:px-16">
            <motion.h2
              className="hero-motion max-w-[12ch] text-[34px] font-extrabold leading-[1.08] tracking-normal text-white text-balance sm:text-[44px] lg:text-[48px]"
              initial={{ opacity: 0, y: 18 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-80px" }}
              transition={{ duration: 0.7, delay: 0.1, ease: easeOut }}
            >
              {l.finalCTATitleLead}
              <span className="font-serif font-medium italic text-orange">{l.finalCTATitleHighlight}</span>
              {l.finalCTATitleTail}
            </motion.h2>

            <motion.p
              className="hero-motion mt-5 max-w-[500px] text-[15px] leading-[1.7] text-white/75 sm:text-[16px]"
              initial={{ opacity: 0, y: 14 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-80px" }}
              transition={{ duration: 0.6, delay: 0.2, ease: easeOut }}
            >
              {l.finalCTASubtitle}
            </motion.p>

            <motion.div
              className="hero-motion mt-7 flex flex-wrap items-center gap-3"
              initial={{ opacity: 0, y: 14 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: "-80px" }}
              transition={{ duration: 0.6, delay: 0.3, ease: easeOut }}
            >
              <a href="/signup" className="btn-primary">
                {l.finalCTACtaPrimary} <ArrowRight size={17} className="btn-arrow" />
              </a>
              <a
                href="/business/register"
                className="inline-flex items-center gap-2 rounded-full border-[1.5px] border-white/70 px-7 py-[15px] text-[15.5px] font-bold text-white transition-colors hover:border-white hover:bg-white/10"
              >
                {l.finalCTACtaSecondary}
              </a>
            </motion.div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
