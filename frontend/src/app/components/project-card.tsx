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
    <article className="project-result">
      <div className="project-result-top">
        <span className="project-tag">
          {p.mode === "personal" ? "Personal · " + p.visibility : p.status}
        </span>
        <span>{d.category}</span>
      </div>
      <h2>
        <Link href={"/projects/" + p.id}>{d.name}</Link>
      </h2>
      <p>{d.description || "Draft description pending."}</p>
      <p className="project-id">ID {p.id}</p>
      <div className="project-result-top">
        <span>
          {d.image_count} images ·{" "}
          {p.mode === "personal"
            ? "0 QC"
            : `${d.reward_per_image} QC / community image`}
        </span>
        <Link
          className="project-link"
          href={
            owner && p.status === "draft"
              ? "/collections/" + p.id + "/edit"
              : "/projects/" + p.id
          }
        >
          {owner && p.status === "draft" ? "Edit draft" : "View project"} →
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
