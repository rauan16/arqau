# ARQAU — Landing Page

A premium fintech landing page for ARQAU (Earned Wage Access + financial
intelligence), built with Next.js 16, React 19, TypeScript, Tailwind CSS v4,
and Framer Motion.

## Getting started

```bash
npm install
npm run dev
```

Open http://localhost:3000.

## Production build

```bash
npm run build
npm run start
```

## Project structure

- `app/` — Next.js App Router entry (`layout.tsx`, `page.tsx`, `globals.css`)
- `components/landing/` — all landing page sections and UI pieces
- `lib/demoData.ts` — single source of truth for every demo number on the
  page, plus the deterministic `evaluateWithdrawal()` logic that powers the
  interactive What-If simulator

## Notes

- All figures (earnings, expenses, employer stats) are fictional demo data
  for the "Pizza Pitch MVP", clearly labeled where shown.
- Fonts (Manrope, Fraunces) are self-hosted via `@fontsource` packages rather
  than fetched from Google Fonts at build time, so the project builds offline
  / behind restrictive network policies without any config changes. Swap to
  `next/font/google` if you prefer and have normal network access.
- No backend, database, or auth — this is a frontend-only concept demo per
  the brief.
