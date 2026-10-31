import { projectApi } from "../../../lib/project-server";
import SubmissionCard from "../../components/submission-card";
import { Pagination } from "../../components/project-card";
export default async function MySubmissions({
  searchParams,
}: {
  searchParams: Promise<{ page?: string }>;
}) {
  const page = Math.min(
    100000,
    Math.max(1, parseInt((await searchParams).page ?? "1", 10) || 1),
  );
  const { client, options } = await projectApi();
  let data;
  try {
    ({ data } = await client.GET("/api/v1/submissions", {
      ...options,
      params: { query: { page, page_size: 10 } },
    }));
  } catch {}
  return (
    <main id="main" className="project-shell">
      <div className="project-heading">
        <div>
          <h1>My Submissions</h1>
          <p>
            Your images, answers, review decisions and earned QC. Approved
            images earn the collection’s configured reward.
          </p>
        </div>
      </div>
      {!data ? (
        <p role="alert">Submissions are unavailable. Please try again.</p>
      ) : data.items.length ? (
        data.items.map((s) => <SubmissionCard key={s.id} submission={s} />)
      ) : (
        <section className="project-panel">
          <p>You haven’t submitted any images yet.</p>
        </section>
      )}
      {data && (
        <Pagination
          page={page}
          size={10}
          total={data.total}
          href={(n) => "/submissions?page=" + n}
        />
      )}
    </main>
  );
}
