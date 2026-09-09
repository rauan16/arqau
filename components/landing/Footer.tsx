const columns = [
  { title: "Product", links: [{ label: "How it works", href: "#how-it-works" }, { label: "Features", href: "#features" }, { label: "Simulator", href: "#simulator" }] },
  { title: "For", links: [{ label: "Employees", href: "#top" }, { label: "Employers", href: "#employers" }, { label: "AI assistant", href: "#ai-assistant" }] },
  { title: "Company", links: [{ label: "Request a demo", href: "/signup" }, { label: "Sign in", href: "/login" }] },
  { title: "Explore", links: [{ label: "Dashboard", href: "/dashboard" }, { label: "Register business", href: "/business/register" }] },
];

export default function Footer() {
  return (
    <footer className="bg-cream border-t border-ink/[0.08] pt-16 pb-10">
      <div className="container-arqau">
        <div className="grid sm:grid-cols-2 lg:grid-cols-[1.4fr_repeat(4,1fr)] gap-10 pb-14">
          <div>
            <p className="text-[19px] font-extrabold tracking-[0.08em] mb-3">ARQAU</p>
            <p className="text-[14px] text-ink-soft max-w-[220px] leading-relaxed">
              Financial intelligence for earned income.
            </p>
            <div className="flex items-center gap-3 mt-6">
              <a href="mailto:hello@arqau.example" aria-label="Email ARQAU" className="w-9 h-9 rounded-full border border-ink/[0.12] flex items-center justify-center text-ink-soft hover:text-ink hover:border-ink/30 transition-colors focus-ring">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                  <path d="M4.98 3.5C4.98 4.88 3.87 6 2.5 6S0 4.88 0 3.5 1.12 1 2.5 1s2.48 1.12 2.48 2.5zM.5 8h4V23h-4V8zm7 0h3.8v2.05h.05c.53-1 1.83-2.05 3.77-2.05 4.03 0 4.78 2.65 4.78 6.1V23h-4v-6.85c0-1.63-.03-3.73-2.27-3.73-2.27 0-2.62 1.77-2.62 3.6V23h-4V8z" />
                </svg>
              </a>
              <a href="/business/register" aria-label="Register your business" className="w-9 h-9 rounded-full border border-ink/[0.12] flex items-center justify-center text-ink-soft hover:text-ink hover:border-ink/30 transition-colors focus-ring">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
                  <rect x="2" y="2" width="20" height="20" rx="5" />
                  <circle cx="12" cy="12" r="4.2" />
                  <circle cx="17.4" cy="6.6" r="1.1" fill="currentColor" stroke="none" />
                </svg>
              </a>
            </div>
          </div>

          {columns.map((col) => (
            <div key={col.title}>
              <p className="text-[13px] font-semibold text-ink-soft mb-4">{col.title}</p>
              <ul className="space-y-3">
                {col.links.map((l) => (
                  <li key={l.label}>
                    <a href={l.href} className="text-[14px] text-ink hover:text-green-deep transition-colors focus-ring">
                      {l.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="pt-8 border-t border-ink/[0.08] text-[13px] text-ink-soft/70">
          © 2026 ARQAU. Demo concept.
        </div>
      </div>
    </footer>
  );
}
