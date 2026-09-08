import type { Metadata } from "next";
import "@fontsource/manrope/400.css";
import "@fontsource/manrope/500.css";
import "@fontsource/manrope/600.css";
import "@fontsource/manrope/700.css";
import "@fontsource/manrope/800.css";
import "@fontsource/fraunces/400-italic.css";
import "@fontsource/fraunces/500-italic.css";
import "./globals.css";
import Providers from "./providers";

export const metadata: Metadata = {
  title: "ARQAU — Smarter Earned Wage Access",
  description:
    "ARQAU helps you access your earned wages and understand how much you should actually withdraw — not just how much you can. Financial intelligence for earned income.",
  openGraph: {
    title: "ARQAU — Smarter Earned Wage Access",
    description:
      "Available is not the same as recommended. ARQAU combines earned income, upcoming expenses and your safety reserve into one clear decision.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
