import Link from "next/link";
import { projectApi } from "../../../lib/project-server";
import { Pagination } from "../../components/project-card";
export default async function Wallet({
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
    ({ data } = await client.GET("/api/v1/wallet", {
      ...options,
      params: { query: { page, page_size: 20 } },
    }));
  } catch {}
  return (
    <main id="main" className="project-shell">
      <div className="project-heading">
        <h1>QPQ Wallet</h1>
      </div>
      {!data ? (
        <p role="alert">Wallet unavailable. Try again.</p>
      ) : (
        <>
          <section className="project-panel">
            <p className="text-3xl font-semibold">
              {data.available} QC available
            </p>
            <p>
              {data.reserved} QC reserved · {data.available + data.reserved} QC
              total
            </p>
            <p>
              Rewards come from the collection’s held credits. Closing returns
              only unspent QC. Eligible accounts receive the welcome grant once.
            </p>
          </section>
          <h2 className="text-xl font-semibold">Transaction history</h2>
          {data.items.map((e) => (
            <article key={e.id} className="project-panel">
              <div className="project-result-top">
                <span>{e.reason.replaceAll("_", " ")}</span>
                <strong>
                  {e.amount > 0 ? "+" : ""}
                  {e.amount} QC
                </strong>
              </div>
              <p>
                {new Date(e.created_at).toLocaleDateString("en-GB", {
                  timeZone: "UTC",
                })}
              </p>
              {e.project_id && (
                <Link
                  className="project-link"
                  href={"/projects/" + e.project_id}
                >
                  View collection
                </Link>
              )}
              {e.submission_id && (
                <p className="project-id">Submission {e.submission_id}</p>
              )}
              <p className="project-id">Ledger entry {e.id}</p>
            </article>
          ))}
          {!data.items.length && <p>No transactions yet.</p>}
          <Pagination
            page={page}
            total={data.total}
            size={20}
            href={(n) => "/wallet?page=" + n}
          />
        </>
      )}
    </main>
  );
}
