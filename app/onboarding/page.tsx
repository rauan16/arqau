"use client";

import { useAuth } from "@/lib/auth-context";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import SmartOnboarding from "@/components/app/SmartOnboarding";

export default function OnboardingPage() {
  const { state, onboardingComplete } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (state === "authenticated" && onboardingComplete) {
      router.push("/dashboard");
    } else if (state === "unauthenticated") {
      router.push("/login");
    }
  }, [state, onboardingComplete, router]);

  if (state === "loading" || state === "unauthenticated" || (state === "authenticated" && onboardingComplete)) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-cream">
        <div className="text-[14px] text-ink-soft">Loading...</div>
      </main>
    );
  }

  return <SmartOnboarding />;
}
