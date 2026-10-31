import Link from "next/link";
import { projectApi } from "../../../lib/project-server";
import { ProjectCard, Pagination } from "../../components/project-card";
export default async function Collections({
  searchParams,
}: {
  searchParams: Promise<{ page?: string }>;
}) {
  const page = Math.min(
    100000,
    Math.max(1, Number.parseInt((await searchParams).page ?? "1", 10) || 1),
  );
  const { client, options } = await projectApi();
  let data;
  try {
    ({ data } = await client.GET("/api/v1/projects/mine", {
      ...options,
      params: { query: { page, page_size: 10 } },
    }));
  } catch {}
  return (
    <main id="main" className="project-shell">
      <div className="project-heading">
        <div>
          <h1>My Collections</h1>
          <p>Draft, preview and manage your research collections.</p>
        </div>
        <Link className="project-button" href="/collections/new">
          Create collection
        </Link>
      </div>
      <p className="mb-6">
        <Link className="project-link" href="/reviews">
          Review submissions →
        </Link>
      </p>
      <section className="project-panel">
        {!data ? (
          <p role="alert">Collections could not be loaded. Try again.</p>
        ) : data.items.length ? (
          data.items.map((p) => (
            <div key={p.id}>
              <ProjectCard project={p} owner />
              <Link
                className="project-link"
                href={"/collections/" + p.id + "/dataset"}
              >
                Dataset publication →
              </Link>
            </div>
          ))
        ) : (
          <p>You haven’t created a collection yet. Start with a draft.</p>
        )}
      </section>
      {data && (
        <Pagination
          page={page}
          total={data.total}
          size={10}
          href={(n) => "/collections?page=" + n}
        />
      )}
    </main>
  );
}
