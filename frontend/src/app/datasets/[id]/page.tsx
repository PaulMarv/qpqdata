import { notFound } from "next/navigation";
import { apiClient } from "../../../lib/api";
import DatasetDownload from "../../components/dataset-download";
import DatasetReport from "../../components/dataset-report";
export default async function Details({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  if (!/^[0-9a-f-]{36}$/.test(id)) notFound();
  const { data: d, response } = await apiClient(
    process.env.QPQ_API_INTERNAL_URL ?? "http://localhost:8000",
  ).GET("/api/v1/datasets/{ident}", {
    cache: "no-store",
    params: { path: { ident: id } },
  });
  if (response.status === 404) notFound();
  if (!d)
    return (
      <main id="main" className="project-shell">
        <p role="alert">Dataset unavailable. Try again.</p>
      </main>
    );
  return (
    <main id="main" className="project-shell">
      <div className="project-heading">
        <div>
          <h1>{d.name}</h1>
          <p>{d.description}</p>
        </div>
      </div>
      <section className="project-panel">
        <p className="project-id">
          Dataset {d.id} · Collection {d.collection_id}
        </p>
        <p>Purpose: {d.purpose}</p>
        <p>
          {d.image_count} approved, authorised images · {d.category} · Criteria
          v{d.criteria_version}
        </p>
        <p>
          Licence: {d.licence} · {d.reuse_terms}
        </p>
        <h2>Labels</h2>
        {d.labels.map((l) => (
          <p key={l.key}>
            {l.name}: {l.description}
          </p>
        ))}
        <h2>Exported metadata fields</h2>
        {(d.criteria.questions ?? []).length ? (
          (d.criteria.questions ?? []).map((q) => (
            <p key={q.key}>
              {q.title} · {q.type} · {q.required ? "required" : "optional"}
              {(q.options ?? []).length
                ? " · " + (q.options ?? []).join(", ")
                : ""}
            </p>
          ))
        ) : (
          <p>Labels only; no additional answers are public.</p>
        )}
        <p>
          ZIP includes images/, labels.csv, manifest.json, README.md and
          LICENSE.txt. Original EXIF/GPS and private account information are
          excluded. Automated validation does not prove originality.
        </p>
      </section>
      <DatasetDownload dataset={d} />
      <DatasetReport id={d.id} />
    </main>
  );
}
