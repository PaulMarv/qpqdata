import { notFound } from "next/navigation";
import { projectApi } from "../../../../../lib/project-server";
import { requireUser } from "../../../../../lib/session";
import ProjectEditor from "../../../../components/project-editor";
export default async function Edit({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const user = await requireUser();
  const { id } = await params;
  if (!/^[0-9a-f-]{36}$/.test(id)) notFound();
  const { client, options } = await projectApi();
  const { data } = await client.GET("/api/v1/projects/{project_id}", {
    ...options,
    params: { path: { project_id: id } },
  });
  if (!data || data.owner_id !== user.id || data.status !== "draft") notFound();
  return <ProjectEditor initial={data} />;
}
