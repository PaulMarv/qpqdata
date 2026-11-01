import Link from "next/link";
import { getReadiness } from "../lib/api";
export const dynamic = "force-dynamic";

export default async function Home() {
  const ready = await getReadiness(
    process.env.QPQ_API_INTERNAL_URL ?? "http://localhost:8000",
  );
  return (
    <div className="home-page mx-auto max-w-6xl px-6 py-8 sm:px-10">
      <main id="main">
        {process.env.QPQ_ENVIRONMENT === "development" &&
          process.env.QPQ_DEV_EMAIL_ENABLED === "true" && (
            <p className="mt-6">
              <Link className="underline" href="/dev-email">
                Test local email verification
              </Link>
            </p>
          )}
        <section className="home-hero py-14 sm:py-20">
          <p className="hero-kicker mb-5 text-sm font-semibold">
            A shared perspective
          </p>
          <h1 className="text-4xl font-semibold leading-tight tracking-tight sm:text-6xl">
            Better datasets start with{" "}
            <span className="hero-emphasis">real perspectives.</span>
          </h1>
          <p className="mt-7 max-w-xl text-lg leading-relaxed text-slate-600">
            Capture, label and organise your own photographs, or collect images
            with a community of students, researchers and professionals.
          </p>
          <p className="mt-8 border-l-2 border-blue-600 pl-4 text-sm leading-relaxed text-slate-600">
            Personal collections start private and cost 0 QC. Approved community
            contributions earn the collection’s QC reward. Published public
            datasets are free to download.
          </p>
          <div className="hero-actions">
            <Link
              href="/projects"
              className="project-button mt-6 inline-block font-semibold"
            >
              Explore community collections →
            </Link>
            <Link href="/datasets" className="project-button secondary mt-6">
              Browse free datasets ↗
            </Link>
          </div>
          <div className="hero-notes">
            <span>Private by default for personal collections</span>
            <span>Capture and label in one flow</span>
            <span>Free public datasets</span>
          </div>
        </section>
        <section
          aria-labelledby="vision"
          className="border-t border-slate-200 py-10"
        >
          <h2 id="vision" className="mb-7 text-2xl font-semibold">
            A little perspective. A lot of possibility.
          </h2>
          <div className="grid gap-8 sm:grid-cols-3">
            {[
              [
                "01",
                "Your images, your collection",
                "Capture and label your own photographs. Personal collections start private, cost no QC and include a private export. Publishing is a separate, explicit choice.",
              ],
              [
                "02",
                "Collect together. Contribute with purpose.",
                "Create a crowdsourced project with clear requirements, or contribute to an accepting collection. Approved community images earn the stated QPQ Credit reward; owner images cost and earn 0 QC.",
              ],
              [
                "03",
                "Published datasets, freely available",
                "Explore explicitly authorised public datasets, review their licence and download images with structured labels. Downloads always cost 0 QC; reuse follows each dataset’s terms.",
              ],
            ].map(([number, title, description]) => (
              <article key={number} className="feature-card">
                <span
                  aria-hidden="true"
                  className="text-sm font-mono text-blue-700"
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
