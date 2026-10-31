import Link from "next/link";
import { projectApi } from "../../lib/project-server";
import { categories } from "../../lib/projects";
import { ProjectCard, Pagination } from "../components/project-card";
export default async function Projects({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const raw = await searchParams;
  const value = (key: string) =>
    typeof raw[key] === "string" ? (raw[key] as string) : "";
  const q = value("q").slice(0, 200),
    category = categories.find((c) => c === value("category")),
    status = (["published", "paused", "closed"] as const).find(
      (s) => s === value("status"),
    );
  const page = Math.min(
      100000,
      Math.max(1, Number.parseInt(value("page"), 10) || 1),
    ),
    sort = value("sort") === "relevance" ? "relevance" : "newest";
  const { client, options } = await projectApi();
  let data;
  try {
    ({ data } = await client.GET("/api/v1/projects", {
      ...options,
      params: { query: { q, category, status, page, page_size: 10, sort } },
    }));
  } catch {}
  const href = (n: number) =>
    "/projects?" +
    new URLSearchParams({
      q,
      category: category ?? "",
      status: status ?? "",
      sort,
      page: String(n),
    });
  return (
    <main id="main" className="project-shell">
      <div className="project-heading">
        <div>
          <p className="project-eyebrow">Explore QPQData</p>
          <h1>Find a collection project</h1>
          <p>Discover image datasets with a clear research purpose.</p>
        </div>
        <Link className="project-button" href="/collections/new">
          Create collection
        </Link>
      </div>
      <section className="project-panel">
        <h2>Search filters</h2>
        <form className="project-filters" action="/projects">
          <label>
            Search by name, ID or keyword
            <input
              name="q"
              defaultValue={q}
              maxLength={200}
              placeholder="e.g. kitchen, biodiversity or project ID"
            />
          </label>
          <label>
            Category
            <select name="category" defaultValue={category ?? ""}>
              <option value="">All categories</option>
              {categories.map((c) => (
                <option key={c}>{c}</option>
              ))}
            </select>
          </label>
          <label>
            Status
            <select name="status" defaultValue={status ?? ""}>
              <option value="">All public statuses</option>
              {["published", "paused", "closed"].map((s) => (
                <option key={s}>{s}</option>
              ))}
            </select>
          </label>
          <label>
            Sort by
            <select name="sort" defaultValue={sort}>
              <option value="newest">Newest</option>
              <option value="relevance">Relevance</option>
            </select>
          </label>
          <button className="project-button">Search</button>
        </form>
      </section>
      <section className="project-panel">
        <h2>Matching projects</h2>
        {!data ? (
          <p role="alert">Projects could not be loaded. Please try again.</p>
        ) : data.items.length ? (
          data.items.map((p) => <ProjectCard key={p.id} project={p} />)
        ) : (
          <p>No matching projects yet.</p>
        )}
      </section>
      {data && (
        <Pagination page={page} total={data.total} size={10} href={href} />
      )}
    </main>
  );
}
