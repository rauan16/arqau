"use client";

import { useAuth } from "@/lib/auth-context";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import AppShell from "@/components/app/AppShell";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { state } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (state === "unauthenticated") {
      router.push("/login");
    }
  }, [state, router]);

  if (state === "loading") {
    return (
      <main className="flex min-h-screen items-center justify-center bg-cream">
        <div className="text-[14px] text-ink-soft">Loading...</div>
      </main>
    );
  }

  if (state === "unauthenticated") {
    return null;
  }

  return <AppShell>{children}</AppShell>;
}
