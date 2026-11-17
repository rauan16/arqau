"use client";

import type { ReactNode } from "react";
import AppShell from "@/components/app/AppShell";
import { demoUserEmail, demoUserName } from "@/lib/demoStore";
import { useLocale } from "@/lib/language-context";

/**
 * The public demo lives in the same shell as the authenticated dashboard, but
 * is rendered with a fictional user object and no auth context. The demo route
 * itself has no guard: it must stay reachable without an account.
 */
export default function DemoLayout({ children }: { children: ReactNode }) {
  const locale = useLocale();
  const demoUser = { name: demoUserName(locale), email: demoUserEmail };

  return (
    <AppShell demoUser={demoUser} isDemo={true}>
      {children}
    </AppShell>
  );
}
