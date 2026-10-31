import Link from "next/link";
import { projectApi } from "../../../lib/project-server";
import { Pagination } from "../../components/project-card";
import ReviewCard from "../../components/review-card";
export default async function Reviews({
  searchParams,
}: {
  searchParams: Promise<{
    project_id?: string;
    status?: string;
    page?: string;
  }>;
}) {
  const q = await searchParams,
    page = Math.min(100000, Math.max(1, parseInt(q.page ?? "1", 10) || 1));
  const status = ["pending", "approved", "rejected"].includes(q.status ?? "")
    ? (q.status as "pending" | "approved" | "rejected")
    : undefined;
  const { client, options } = await projectApi();
  let data;
  try {
    ({ data } = await client.GET("/api/v1/moderation", {
      ...options,
      params: {
        query: { project_id: q.project_id, status, page, page_size: 10 },
      },
    }));
  } catch {}
  return (
    <main id="main" className="project-shell">
      <div className="project-heading">
        <div>
          <h1>Review submissions</h1>
          <p>
            Review images for your collections and collections you moderate.
          </p>
        </div>
        <Link className="project-link" href="/collections">
          My Collections
        </Link>
      </div>
      {!data ? (
        <p role="alert">Reviews could not be loaded. Try again.</p>
      ) : (
        <>
          <section className="project-panel">
            <p>
              {data.pending} pending · {data.approved} approved ·{" "}
              {data.rejected} rejected
            </p>
            <form className="project-form" method="get">
              <label>
                Collection
                <select name="project_id" defaultValue={q.project_id ?? ""}>
                  <option value="">All collections</option>
                  {data.collections.map((c) => (
                    <option key={c.project_id} value={c.project_id}>
                      {c.project_name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Review status
                <select name="status" defaultValue={status ?? ""}>
                  <option value="">All review statuses</option>
                  <option value="pending">Pending</option>
                  <option value="approved">Approved</option>
                  <option value="rejected">Rejected</option>
                </select>
              </label>
              <button className="project-button">Apply filters</button>
            </form>
          </section>
          {data.collections.map((c) => (
            <section className="project-panel" key={c.project_id}>
              <h2>{c.project_name}</h2>
              <p>
                {c.requested} requested · {c.uploading} uploading · {c.pending}{" "}
                pending · {c.approved} approved · {c.rejected} rejected
              </p>
              <p>
                {c.remaining_reserved_qc} QC held ·{" "}
                {c.remaining_funded_approvals} remaining funded approvals
                (includes pending images)
              </p>
            </section>
          ))}
          {data.items.length ? (
            data.items.map((item) => (
              <ReviewCard key={item.submission.id} item={item} />
            ))
          ) : (
            <section className="project-panel">
              No submissions match these filters.
            </section>
          )}
          <Pagination
            page={page}
            total={data.total}
            size={10}
            href={(n) =>
              "/reviews?" +
              new URLSearchParams({
                ...(q.project_id ? { project_id: q.project_id } : {}),
                ...(status ? { status } : {}),
                page: String(n),
              })
            }
          />
        </>
      )}
    </main>
  );
}
