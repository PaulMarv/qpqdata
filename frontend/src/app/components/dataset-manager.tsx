"use client";
/* eslint-disable @next/next/no-img-element -- authenticated private source images must bypass public optimisation */
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { datasetAction, type Dataset } from "../../lib/datasets";
import type { Project } from "../../lib/projects";
import type { components } from "../../lib/api-schema";
export default function DatasetManager({
  project: p,
  initial,
  review,
  reports,
}: {
  project: Project;
  initial: Dataset | null;
  review: components["schemas"]["ExportReview"][];
  reports: components["schemas"]["DatasetReportView"][];
}) {
  const [busy, setBusy] = useState(false),
    [message, setMessage] = useState("");
  const router = useRouter();
  async function action(path: string, body: unknown = {}) {
    setBusy(true);
    setMessage("");
    try {
      await datasetAction(path, body);
      setMessage("Saved. Dataset distribution never changes QC balances.");
      router.refresh();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Request failed.");
    } finally {
      setBusy(false);
    }
  }
  const supported = ["CC0-1.0", "CC-BY-4.0", "CC-BY-SA-4.0"].includes(
    p.definition.licence ?? "",
  );
  return (
    <main id="main" className="project-shell">
      <div className="project-heading">
        <div>
          <h1>Publish dataset</h1>
          <p>
            {p.definition.name} · {p.id}
          </p>
        </div>
      </div>
      <section className="project-panel">
        <p>
          Approval and QC payout do not authorise public distribution. Every
          image needs contributor export consent and your separate
          distribution/privacy review. No existing image is automatically
          public.
        </p>
        <p>
          Licence: {p.definition.licence} · {p.definition.reuse_terms}
        </p>
      </section>
      {!initial ? (
        <form
          className="project-panel project-form"
          onSubmit={(e) => {
            e.preventDefault();
            const f = new FormData(e.currentTarget);
            action("start/" + p.id, {
              criteria_version: p.published_version,
              public_fields: f.getAll("field"),
              distribution_authorised: true,
              privacy_reviewed: true,
            });
          }}
        >
          <h2>Public metadata policy</h2>
          <p>
            Only selected structured fields and labels are public. Text answers
            remain private. This policy is frozen after publication.
          </p>
          {(p.definition.criteria?.questions ?? [])
            .filter((q) => q.type !== "short_text")
            .map((q) => (
              <label key={q.key} className="dataset-check">
                <input type="checkbox" name="field" value={q.key} />
                {q.title}
              </label>
            ))}
          <label className="dataset-check">
            <input type="checkbox" required />I authorise public dataset
            distribution under the recorded licence/reuse terms and have
            reviewed their compatibility and my right to publish the
            labels/schema.
          </label>
          <label className="dataset-check">
            <input type="checkbox" required />I reviewed the public
            descriptions/schema for privacy. Each image will receive a separate
            rights and privacy review.
          </label>
          {(!supported || !p.published_version) && (
            <p role="alert">
              Publish the collection with a supported standard licence first.
              Custom licences require separate review.
            </p>
          )}
          <button
            className="project-button"
            disabled={busy || !supported || !p.published_version}
          >
            Authorise dataset publication
          </button>
        </form>
      ) : (
        <>
          <section className="project-panel">
            <Link className="project-link" href={"/datasets/" + initial.id}>
              View public dataset
            </Link>
            <p>
              Each snapshot includes the current approved, opted-in and
              owner-authorised images. Newly authorised images require a new
              version.
            </p>
            <button
              className="project-button"
              disabled={busy}
              onClick={() => action(initial.id + "/versions")}
            >
              Publish current image set as a version
            </button>
            <button
              className="project-link"
              disabled={busy}
              onClick={() => action(initial.id + "/withdraw")}
            >
              Withdraw entire dataset (permanent for this policy)
            </button>
          </section>
          <h2 className="text-xl font-semibold">Image distribution review</h2>
          {review.length ? (
            review.map((r) => (
              <article className="project-panel" key={r.submission_id}>
                <p className="project-id">Submission {r.submission_id}</p>
                <img
                  className="contribution-preview"
                  src={`/api/moderation/${r.submission_id}/image`}
                  alt={"Approved image labelled " + r.label}
                />
                <p>Label: {r.label}</p>
                <pre className="whitespace-pre-wrap break-words">
                  {JSON.stringify(r.answers, null, 2)}
                </pre>
                <p>
                  Public attribution:{" "}
                  {r.consent.public_attribution || "None requested"}
                </p>
                {!r.consent.id ? (
                  <p>Waiting for contributor export opt-in.</p>
                ) : r.consent.withdrawn ? (
                  <p>
                    Distribution permission withdrawn. Excluded from future
                    exports.
                  </p>
                ) : r.consent.authorised ? (
                  <>
                    <p>Export authorised.</p>
                    <button
                      className="project-link"
                      disabled={busy}
                      onClick={() =>
                        action(
                          `${initial.id}/withdraw-image/${r.submission_id}`,
                        )
                      }
                    >
                      Withdraw image distribution permission
                    </button>
                  </>
                ) : (
                  <form
                    className="project-form"
                    onSubmit={(e) => {
                      e.preventDefault();
                      action(`${initial.id}/authorise/${r.submission_id}`, {
                        consent_id: r.consent.id,
                        distribution_authorised: true,
                        privacy_reviewed: true,
                      });
                    }}
                  >
                    <label className="dataset-check">
                      <input type="checkbox" required />I reviewed this image
                      and its public answers; rights, licence, public
                      distribution and privacy are appropriate. Automated checks
                      cannot prove originality or suitability.
                    </label>
                    <button className="project-button" disabled={busy}>
                      Authorise image for export
                    </button>
                  </form>
                )}
              </article>
            ))
          ) : (
            <p>No approved images yet.</p>
          )}
          <section className="project-panel">
            <h2>Dataset reports</h2>
            {!reports.length ? (
              <p>No reports.</p>
            ) : (
              reports.map((r) => (
                <article className="project-inset" key={r.id}>
                  <p>
                    {r.reason}: {r.details}
                  </p>
                  <p className="project-id">
                    Image: {r.image_id ?? "Entire dataset"} · Submission:{" "}
                    {r.submission_id ?? "Not specified"}
                  </p>
                  <Link
                    className="project-link"
                    href={"/reviews?project_id=" + p.id}
                  >
                    Review and restrict the affected image
                  </Link>
                </article>
              ))
            )}
          </section>
        </>
      )}
      <p role="status">{message}</p>
    </main>
  );
}
