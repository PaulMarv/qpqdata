"use client";
import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { projectMutation, type Project } from "../../lib/projects";
export default function ProjectActions({ project: p }: { project: Project }) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const router = useRouter();
  async function change(status: "published" | "paused" | "closed") {
    if (
      status === "closed" &&
      !window.confirm(
        "Close this collection permanently and release its reserved QC?",
      )
    )
      return;
    if (
      status === "published" &&
      p.status === "draft" &&
      !window.confirm(
        `Publish this version and reserve ${p.budget} QC? Its definition will be frozen.`,
      )
    )
      return;
    setBusy(true);
    setError("");
    try {
      await projectMutation("/" + p.id + "/status", "POST", {
        status,
        expected_version: p.version,
      });
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Please try again.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="project-panel">
      <h2>Manage collection</h2>
      <p>
        {p.reserved_credits} QC reserved · {p.budget} QC budget
      </p>
      <p>
        Publishing freezes the full definition. Pausing retains the reservation;
        closing permanently releases it. New criteria require a new project.
        Pending images keep the budget reserved; pause the collection to stop
        new contributions.
      </p>
      <div className="project-actions">
        {p.status === "draft" && (
          <>
            <Link
              className="project-button secondary"
              href={"/collections/" + p.id + "/edit"}
            >
              Edit draft
            </Link>
            <button
              disabled={busy}
              className="project-button"
              onClick={() => change("published")}
            >
              Publish · reserve {p.budget} QC
            </button>
          </>
        )}
        {p.status === "published" && (
          <button
            disabled={busy}
            className="project-button"
            onClick={() => change("paused")}
          >
            Pause collection
          </button>
        )}
        {p.status === "paused" && (
          <button
            disabled={busy}
            className="project-button"
            onClick={() => change("published")}
          >
            Resume collection
          </button>
        )}
        {p.status !== "closed" && (
          <button
            disabled={busy}
            className="project-button secondary"
            onClick={() => change("closed")}
          >
            Close collection
          </button>
        )}
      </div>
      {error && (
        <p role="alert" className="project-error">
          {error}
        </p>
      )}
    </section>
  );
}
