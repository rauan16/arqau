"use client";

import { useTranslation } from "@/lib/language-context";
import BrandLogo from "@/components/ui/BrandLogo";

const socials = [
  { label: "X", path: "M18.9 1.2h3.7l-8 9.2 9.4 12.4h-7.4l-5.8-7.6-6.6 7.6H.5l8.6-9.8L0 1.2h7.6l5.4 7.1 5.9-7.1Zm-1.3 19.1h2L6.4 3.2h-2l13.2 17.1Z" },
  {
    label: "Instagram",
    path: "M12 2.2c3.2 0 3.6 0 4.9.1 1.2.1 1.8.2 2.2.4.6.2 1 .5 1.4.9.4.4.7.8.9 1.4.2.4.4 1 .4 2.2.1 1.3.1 1.7.1 4.9s0 3.6-.1 4.9c-.1 1.2-.2 1.8-.4 2.2-.2.6-.5 1-.9 1.4-.4.4-.8.7-1.4.9-.4.2-1 .4-2.2.4-1.3.1-1.7.1-4.9.1s-3.6 0-4.9-.1c-1.2-.1-1.8-.2-2.2-.4-.6-.2-1-.5-1.4-.9-.4-.4-.7-.8-.9-1.4-.2-.4-.4-1-.4-2.2C2.2 15.6 2.2 15.2 2.2 12s0-3.6.1-4.9c.1-1.2.2-1.8.4-2.2.2-.6.5-1 .9-1.4.4-.4.8-.7 1.4-.9.4-.2 1-.4 2.2-.4C8.4 2.2 8.8 2.2 12 2.2Zm0 1.8c-3.1 0-3.5 0-4.7.1-.9 0-1.4.2-1.7.3-.4.2-.7.3-1 .6-.3.3-.4.6-.6 1-.1.3-.3.8-.3 1.7-.1 1.2-.1 1.6-.1 4.7s0 3.5.1 4.7c0 .9.2 1.4.3 1.7.2.4.3.7.6 1 .3.3.6.4 1 .6.3.1.8.3 1.7.3 1.2.1 1.6.1 4.7.1s3.5 0 4.7-.1c.9 0 1.4-.2 1.7-.3.4-.2.7-.3 1-.6.3-.3.4-.6.6-1 .1-.3.3-.8.3-1.7.1-1.2.1-1.6.1-4.7s0-3.5-.1-4.7c0-.9-.2-1.4-.3-1.7a2.6 2.6 0 0 0-.6-1c-.3-.3-.6-.4-1-.6-.3-.1-.8-.3-1.7-.3-1.2-.1-1.6-.1-4.7-.1Zm0 3.1a4.9 4.9 0 1 1 0 9.8 4.9 4.9 0 0 1 0-9.8Zm0 1.8a3.1 3.1 0 1 0 0 6.2 3.1 3.1 0 0 0 0-6.2Zm5.2-2.1a1.2 1.2 0 1 1 0 2.3 1.2 1.2 0 0 1 0-2.3Z",
  },
  {
    label: "LinkedIn",
    path: "M6.9 20.5H2.6V8.6h4.3v11.9ZM4.7 6.7a2.2 2.2 0 1 1 0-4.5 2.2 2.2 0 0 1 0 4.5ZM21.4 20.5h-4.3v-6.2c0-1.7 0-3.4-2-3.4s-2.2 1.5-2.2 3.3v6.3H8.6V8.6h4v1.6h.1c.6-1 1.9-2 3.8-2 3 0 3.9 1.9 3.9 5.1v7.2Z",
  },
  {
    label: "YouTube",
    path: "M21.6 6.2a2.5 2.5 0 0 0-1.8-1.8C18 4 12 4 12 4s-6 0-7.8.4A2.5 2.5 0 0 0 2.4 6.2C2 8 2 12 2 12s0 4 .4 5.8a2.5 2.5 0 0 0 1.8 1.8C6 20 12 20 12 20s6 0 7.8-.4a2.5 2.5 0 0 0 1.8-1.8C22 16 22 12 22 12s0-4-.4-5.8ZM10 15.5v-7l6 3.5-6 3.5Z",
  },
];

export default function Footer() {
  const { t } = useTranslation();
  const l = t.landing;

  const columns = [
    {
      title: l.footerProduct,
      links: [
        { label: l.footerFeatures, href: "#product" },
        { label: t.nav.pricing, href: "#pricing" },
        { label: l.footerIntegrations, href: "#faq" },
      ],
    },
    {
      title: l.footerCompany,
      links: [
        { label: t.nav.about, href: "#about" },
        { label: l.footerContact, href: "/business/register" },
      ],
    },
    { title: l.footerLegal, links: [] as { label: string; href: string }[] },
  ];

  return (
    <footer className="border-t border-border bg-cream">
      <div className="container-arqau py-10 sm:py-12 lg:py-14">
        <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-[1.5fr_repeat(3,1fr)_auto] lg:gap-8">
          <div>
            <div className="flex items-center gap-2.5">
              <BrandLogo size={48} />
              <span className="text-[20px] font-extrabold tracking-[-0.02em] text-ink">{t.brand}</span>
            </div>
            <p className="mt-4 max-w-[260px] text-[14px] leading-relaxed text-ink-soft">{l.footerTagline}</p>
          </div>

          {columns.map((col) => (
            <div key={col.title}>
              <p className="mb-3 text-[13px] font-bold text-ink">{col.title}</p>
              {col.links.length > 0 ? (
                <ul className="space-y-3">
                  {col.links.map((link) => (
                    <li key={link.label}>
                      <a href={link.href} className="text-[13.5px] text-ink-soft transition-colors hover:text-orange focus-ring">
                        {link.label}
                      </a>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-[13px] leading-relaxed text-ink-muted">{l.footerLegalNote}</p>
              )}
            </div>
          ))}

          {/* Decorative icon set only: the platform URLs were not supplied, so these remain non-interactive. */}
          <div className="flex items-center gap-2 sm:col-span-2 lg:col-span-1 lg:justify-end" aria-hidden="true" role="presentation">
            {socials.map((s) => (
              <span
                key={s.label}
                title={s.label}
                aria-hidden="true"
                className="pointer-events-none flex h-9 w-9 items-center justify-center rounded-full border border-border text-ink-soft"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                  <path d={s.path} />
                </svg>
              </span>
            ))}
          </div>
        </div>

        <div className="mt-10 border-t border-border pt-6 text-[12px] text-ink-muted">{l.footerRights}</div>
      </div>
    </footer>
  );
}
