import { Suspense } from "react";
import { ComingSoon } from "@/components/app/ComingSoon";

export default function Page() {
  return (
    <Suspense fallback={null}>
      <ComingSoon />
    </Suspense>
  );
}