import Link from "next/link";
import type { Project } from "../../lib/projects";
export function ProjectCard({
  project: p,
  owner = false,
}: {
  project: Project;
  owner?: boolean;
}) {
  const d = p.definition;
  return (
    <article className="project-result collection-card">
      <div className="card-content">
        <div className="card-badges">
          <span className="project-tag">
            {p.mode === "personal" ? "Personal · " + p.visibility : p.status}
          </span>
          <span className="category-chip">{d.category}</span>
        </div>
        <h2 className="card-title">
          <Link href={"/projects/" + p.id}>{d.name}</Link>
        </h2>
        <p className="card-description">
          {d.description || "Draft description pending."}
        </p>
        <p className="project-id card-reference">Project ID {p.id}</p>
      </div>
      <div className="card-summary">
        <dl className="card-metrics">
          <div>
            <dt>
              {p.mode === "personal" ? "Image capacity" : "Images requested"}
            </dt>
            <dd>{d.image_count.toLocaleString("en-GB")}</dd>
          </div>
          <div>
            <dt>
              {p.mode === "personal" ? "Collection cost" : "Community reward"}
            </dt>
            <dd className="card-reward">
              <span className="credit-badge">
                {p.mode === "personal"
                  ? "0 QC"
                  : `${d.reward_per_image} QC / community image`}
              </span>
            </dd>
          </div>
        </dl>
        <Link
          className="card-action"
          href={
            owner && p.status === "draft"
              ? "/collections/" + p.id + "/edit"
              : "/projects/" + p.id
          }
        >
          {owner && p.status === "draft" ? "Edit draft" : "View project"}{" "}
          <span aria-hidden="true">→</span>
        </Link>
      </div>
    </article>
  );
}
export function Pagination({
  page,
  total,
  size,
  href,
}: {
  page: number;
  total: number;
  size: number;
  href: (n: number) => string;
}) {
  const pages = Math.max(1, Math.ceil(total / size));
  return (
    <nav aria-label="Project pages" className="project-pagination">
      {page > 1 && <Link href={href(page - 1)}>← Previous</Link>}
      <span>
        Page {page} of {pages} · {total} projects
      </span>
      {page < pages && <Link href={href(page + 1)}>Next →</Link>}
    </nav>
  );
}
