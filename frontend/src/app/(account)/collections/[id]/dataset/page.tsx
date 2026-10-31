import { notFound } from "next/navigation";
import { projectApi } from "../../../../../lib/project-server";
import { requireUser } from "../../../../../lib/session";
import DatasetManager from "../../../../components/dataset-manager";
export default async function Manage({
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
  if (!p || p.owner_id !== user.id) notFound();
  const { data: d, response } = await client.GET(
    "/api/v1/projects/{project_id}/dataset",
    { ...options, params: { path: { project_id: id } } },
  );
  if (!response.ok)
    return (
      <main id="main" className="project-shell">
        <p role="alert">Dataset publication unavailable in this environment.</p>
      </main>
    );
  let review, reports;
  if (d) {
    ({ data: review } = await client.GET("/api/v1/datasets/{ident}/review", {
      ...options,
      params: { path: { ident: d.id } },
    }));
    ({ data: reports } = await client.GET("/api/v1/datasets/{ident}/reports", {
      ...options,
      params: { path: { ident: d.id } },
    }));
  }
  return (
    <DatasetManager
      project={p}
      initial={d ?? null}
      review={review ?? []}
      reports={reports ?? []}
    />
  );
}
