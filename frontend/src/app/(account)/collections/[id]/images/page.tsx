import Link from "next/link";
import { notFound } from "next/navigation";
import { projectApi } from "../../../../../lib/project-server";
import { requireUser } from "../../../../../lib/session";
import PersonalImage from "../../../../components/personal-image";
import { Pagination } from "../../../../components/project-card";
export default async function Images({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ page?: string; label?: string }>;
}) {
  const user = await requireUser(),
    { id } = await params,
    query = await searchParams;
  if (!/^[0-9a-f-]{36}$/.test(id)) notFound();
  const page = Math.max(
    1,
    Math.min(100000, Number.parseInt(query.page ?? "1", 10) || 1),
  );
  const { client, options } = await projectApi();
  const { data: p } = await client.GET("/api/v1/projects/{project_id}", {
    ...options,
    params: { path: { project_id: id } },
  });
  if (!p || p.owner_id !== user.id) notFound();
  const { data } = await client.GET(
    "/api/v1/projects/{project_id}/owner-images",
    {
      ...options,
      params: {
        path: { project_id: id },
        query: { page, page_size: 20, label: query.label || undefined },
      },
    },
  );
  return (
    <main id="main" className="project-shell">
      <p className="project-eyebrow">QPQDATA / COLLECTIONS</p>
      <h1>{p.definition.name}</h1>
      <p>
        {p.mode} · {p.visibility} · {p.owner_images} owner images · 0 QC for
        owner images
      </p>
      {p.mode !== "personal" && (
        <p>
          {p.community_images} approved community images · {p.remaining_slots}{" "}
          unfilled target slots · {p.reserved_credits} QC held until payout or
          closure. Owner images never displace pending contributions.
        </p>
      )}
      <div className="project-actions">
        <Link className="project-button" href={`/projects/${id}/contribute`}>
          Add more photos
        </Link>
        {p.mode === "personal" && (
          <a
            className="project-button secondary"
            href={`/api/private-export/${id}`}
          >
            Export privately · 0 QC
          </a>
        )}
        <Link
          className="project-button secondary"
          href={`/collections/${id}/dataset`}
        >
          Review publication
        </Link>
      </div>
      <section className="project-panel">
        <h2>Gallery and labels</h2>
        <form className="project-filters">
          <label>
            Filter by label
            <select name="label" defaultValue={query.label ?? ""}>
              <option value="">All labels</option>
              {p.definition.labels?.map((l) => (
                <option key={l.key} value={l.key}>
                  {l.name}
                </option>
              ))}
            </select>
          </label>
          <button className="project-button">Filter</button>
        </form>
      </section>
      {!data ? (
        <p role="alert">Images could not be loaded.</p>
      ) : (
        <>
          <div className="owner-gallery">
            {data.items.map((s) => (
              <PersonalImage
                key={s.id + s.annotation_hash}
                submission={s}
                definition={p.definition}
                editable={p.mode === "personal"}
              />
            ))}
          </div>
          {!data.items.length && <p>No images yet. Add your first photo.</p>}
          <Pagination
            page={page}
            total={data.total}
            size={20}
            href={(n) =>
              `/collections/${id}/images?` +
              new URLSearchParams({ page: String(n), label: query.label ?? "" })
            }
          />
        </>
      )}
    </main>
  );
}
