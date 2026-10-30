import Link from "next/link";
import { getReadiness } from "../lib/api";
export const dynamic = "force-dynamic";

export default async function Home() {
  const ready = await getReadiness(
    process.env.QPQ_API_INTERNAL_URL ?? "http://localhost:8000",
  );
  return (
    <div className="mx-auto max-w-6xl px-6 py-8 sm:px-10">
      <header className="flex items-center justify-between gap-4 border-b border-slate-200 pb-6">
        <Link href="/" className="text-xl font-bold tracking-tight">
          QPQ<span className="text-teal-700">Data</span>
        </Link>
        <span className="rounded-full bg-teal-50 px-3 py-1 text-xs font-semibold text-teal-900">
          Phase 1 · Foundation
        </span>
      </header>
      <main id="main">
        <section className="max-w-3xl py-20 sm:py-28">
          <p className="mb-5 text-sm font-semibold uppercase tracking-widest text-teal-700">
            A shared perspective
          </p>
          <h1 className="text-4xl font-semibold leading-tight tracking-tight sm:text-6xl">
            Better datasets start with real perspectives.
          </h1>
          <p className="mt-7 max-w-xl text-lg leading-relaxed text-slate-600">
            A space for students, researchers, and professionals to build image
            collections together. Contribute original photographs. Support
            useful research.
          </p>
          <p className="mt-8 border-l-2 border-teal-600 pl-4 text-sm leading-relaxed text-slate-600">
            We’re building the foundation. Project creation, contributions,
            accounts, and dataset downloads are not available yet.
          </p>
        </section>
        <section
          aria-labelledby="vision"
          className="border-t border-slate-200 py-10"
        >
          <h2 id="vision" className="mb-7 text-2xl font-semibold">
            What we’re working toward
          </h2>
          <div className="grid gap-8 sm:grid-cols-3">
            {[
              [
                "01",
                "Collections with clarity",
                "Named projects with clear image requirements, labels, and structured metadata.",
              ],
              [
                "02",
                "Contributions with value",
                "Original photographs, with QPQ Credits earned for approved contributions.",
              ],
              [
                "03",
                "Knowledge for everyone",
                "Published datasets available to download for free.",
              ],
            ].map(([number, title, description]) => (
              <article key={number}>
                <span
                  aria-hidden="true"
                  className="text-sm font-mono text-teal-700"
                >
                  {number}
                </span>
                <h3 className="mt-3 font-semibold">{title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-slate-600">
                  {description}
                </p>
              </article>
            ))}
          </div>
        </section>
      </main>
      <footer className="mt-10 flex flex-wrap justify-between gap-4 border-t border-slate-200 py-6 text-xs text-slate-600">
        <p>QPQData · Built for shared discovery</p>
        <p role="status">API: {ready ? "ready" : "unavailable"}</p>
      </footer>
    </div>
  );
}
