import Link from "next/link";
import { notFound } from "next/navigation";
import { projectApi } from "../../../lib/project-server";
import { currentUser } from "../../../lib/session";
import ProjectDefinition from "../../components/project-definition";
import ProjectActions from "../../components/project-actions";
export default async function Detail({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  if (!/^[0-9a-f-]{36}$/.test(id)) notFound();
  const { client, options } = await projectApi();
  let result;
  try {
    result = await client.GET("/api/v1/projects/{project_id}", {
      ...options,
      params: { path: { project_id: id } },
    });
  } catch {}
  if (result?.response.status === 404) notFound();
  const p = result?.data;
  if (!p)
    return (
      <main id="main" className="project-shell">
        <p role="alert">Project could not be loaded. Please try again.</p>
      </main>
    );
  const user = await currentUser();
  return (
    <main id="main" className="project-shell">
      <Link className="project-link" href="/projects">
        ← Explore projects
      </Link>
      <div className="project-heading">
        <div>
          <p className="project-eyebrow">
            {p.definition.category} · {p.status}
          </p>
          <h1>{p.definition.name}</h1>
          <p className="project-id">
            Project ID {p.id} · Definition v{p.version}
          </p>
        </div>
        <span className="project-tag">{p.status}</span>
      </div>
      {user?.id === p.owner_id && <ProjectActions project={p} />}
      <ProjectDefinition definition={p.definition} />
      <section className="project-panel">
        <h2>Contributing</h2>
        {p.closing_date_passed && <p>The closing date has passed.</p>}
        <p>Image contributions are not available yet.</p>
        {!user && (
          <p>
            <Link className="project-link" href="/login">
              Log in
            </Link>{" "}
            or{" "}
            <Link className="project-link" href="/signup">
              sign up
            </Link>{" "}
            with an eligible school or work email before contributing.
          </p>
        )}
      </section>
    </main>
  );
}
