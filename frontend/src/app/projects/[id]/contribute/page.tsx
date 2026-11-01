import Link from "next/link";
import { notFound } from "next/navigation";
import { requireUser } from "../../../../lib/session";
import { projectApi } from "../../../../lib/project-server";
import QuickCapture from "../../../components/quick-capture";
export default async function Contribute({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const user = await requireUser(),
    { id } = await params;
  if (!/^[0-9a-f-]{36}$/.test(id)) notFound();
  const { client, options } = await projectApi();
  const { data: p } = await client.GET("/api/v1/projects/{project_id}", {
    ...options,
    params: { path: { project_id: id } },
  });
  if (!p) notFound();
  const error =
    process.env.QPQ_UPLOADS_ENABLED !== "true"
      ? "Image contributions are not enabled in this environment."
      : (p.status !== "published" &&
            !(p.owner_id === user.id && p.status === "paused")) ||
          p.closing_date_passed
        ? "This collection is not accepting images."
        : null;
  if (error)
    return (
      <main id="main" className="project-shell">
        <h1>Contribution unavailable</h1>
        <p>{error}</p>
        <Link href={"/projects/" + id} className="project-link">
          Back to collection
        </Link>
      </main>
    );
  return <QuickCapture key={p.id} project={p} owner={p.owner_id === user.id} />;
}
