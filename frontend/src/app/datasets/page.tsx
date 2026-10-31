import Link from "next/link";
import { apiClient } from "../../lib/api";
import { Pagination } from "../components/project-card";
export default async function Library({
  searchParams,
}: {
  searchParams: Promise<{
    q?: string;
    category?: string;
    licence?: string;
    sort?: string;
    page?: string;
  }>;
}) {
  const q = await searchParams,
    page = Math.min(100000, Math.max(1, parseInt(q.page ?? "1", 10) || 1));
  const sort = ["updated", "newest", "relevance"].includes(q.sort ?? "")
    ? (q.sort as "updated" | "newest" | "relevance")
    : "updated";
  let data;
  try {
    ({ data } = await apiClient(
      process.env.QPQ_API_INTERNAL_URL ?? "http://localhost:8000",
    ).GET("/api/v1/datasets", {
      cache: "no-store",
      signal: AbortSignal.timeout(8000),
      params: {
        query: {
          q: q.q,
          category: q.category,
          licence: q.licence,
          sort,
          page,
          page_size: 12,
        },
      },
    }));
  } catch {}
  return (
    <main id="main" className="project-shell">
      <div className="project-heading">
        <div>
          <h1>Dataset library</h1>
          <p>
            Explicitly authorised image datasets. Free downloads, always 0 QC.
          </p>
        </div>
      </div>
      <form className="project-panel project-form" method="get">
        <label>
          Search datasets
          <input
            name="q"
            defaultValue={q.q}
            maxLength={200}
            placeholder="Name, collection ID or keyword"
          />
        </label>
        <label>
          Category
          <select name="category" defaultValue={q.category ?? ""}>
            <option value="">All categories</option>
            {[
              "science",
              "education",
              "environment",
              "health",
              "technology",
              "society",
              "other",
            ].map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <label>
          Licence
          <select name="licence" defaultValue={q.licence ?? ""}>
            <option value="">All licences</option>
            {["CC0-1.0", "CC-BY-4.0", "CC-BY-SA-4.0"].map((c) => (
              <option key={c}>{c}</option>
            ))}
          </select>
        </label>
        <label>
          Sort
          <select name="sort" defaultValue={sort}>
            <option value="updated">Recently updated</option>
            <option value="newest">Newest</option>
            <option value="relevance">Relevance</option>
          </select>
        </label>
        <button className="project-button">Search datasets</button>
      </form>
      {!data ? (
        <p role="alert">Dataset library unavailable. Try again.</p>
      ) : !data.items.length ? (
        <section className="project-panel">
          No published datasets match your search.
        </section>
      ) : (
        data.items.map((d) => (
          <article key={d.id} className="project-panel">
            <div className="project-result-top">
              <h2>
                <Link className="project-link" href={"/datasets/" + d.id}>
                  {d.name}
                </Link>
              </h2>
              <span className="project-tag">Free · 0 QC</span>
            </div>
            <p>{d.description}</p>
            <p className="project-id">Collection {d.collection_id}</p>
            <p>
              {d.category} · {d.image_count} available approved images ·{" "}
              {d.licence}
            </p>
            <p>
              {d.labels.map((l) => l.name).join(", ")} · Criteria v
              {d.criteria_version}
            </p>
            <p>
              Updated{" "}
              {new Date(d.updated_at).toLocaleDateString("en-GB", {
                timeZone: "UTC",
              })}
            </p>
            <p>
              {d.versions.some((v) => v.downloadable)
                ? "ZIP available"
                : "Preparation or owner publication required"}
            </p>
          </article>
        ))
      )}
      {data && (
        <Pagination
          page={page}
          total={data.total}
          size={12}
          href={(n) =>
            "/datasets?" + new URLSearchParams({ ...q, page: String(n) })
          }
        />
      )}
    </main>
  );
}
