"use client";
/* eslint-disable @next/next/no-img-element -- private images require authenticated access without a public optimiser */
import { useState } from "react";
import { useRouter } from "next/navigation";
import type { components } from "../../lib/api-schema";
export default function ReviewCard({
  item,
}: {
  item: components["schemas"]["ReviewItem"];
}) {
  const s = item.submission,
    router = useRouter();
  const [reason, setReason] = useState(""),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState("");
  async function decide(outcome: "approved" | "rejected") {
    if (outcome === "rejected" && !reason.trim()) {
      setMessage("Enter a rejection reason.");
      return;
    }
    setBusy(true);
    setMessage("");
    try {
      const r = await fetch(`/api/moderation/${s.id}/decision`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          outcome,
          reason: outcome === "rejected" ? reason.trim() : "",
        }),
      });
      const data = await r.json();
      if (!r.ok)
        throw new Error(
          typeof data.detail === "string" ? data.detail : "Decision failed.",
        );
      setMessage(
        outcome === "approved"
          ? `Approved · ${data.qc_earned} QC awarded.`
          : "Rejected. Outcome notification queued.",
      );
      router.refresh();
    } catch (e) {
      setMessage(
        e instanceof Error ? e.message : "Review unavailable. Retry safely.",
      );
    } finally {
      setBusy(false);
    }
  }
  async function restrict() {
    setBusy(true);
    setMessage("");
    try {
      const r = await fetch(`/api/moderation/${s.id}/removal-request`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          reason: "other",
          details: "Collection reviewer requested removal.",
        }),
      });
      if (!r.ok)
        throw new Error("Could not restrict this image. Retry safely.");
      setMessage("Image access revoked. Earned QC is retained.");
      router.refresh();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Request failed.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <article className="project-panel project-form">
      <div className="project-result-top">
        <h2>{s.project_name}</h2>
        <span className="project-tag">
          {s.status === "pending" ? "Pending Review" : s.status}
        </span>
      </div>
      <p className="project-id">
        Submission {s.id} · Definition v{s.criteria_version}
      </p>
      <p>
        Contributor: {item.contributor_name} · Label: {s.label_name}
      </p>
      {!s.hidden && !s.image_deleted ? (
        <img
          className="contribution-preview"
          src={`/api/moderation/${s.id}/image`}
          alt={`Submitted image labelled ${s.label_name}`}
        />
      ) : (
        <p role="note">
          Image unavailable under the removal or retention policy. Approval is
          blocked.
        </p>
      )}
      <dl className="project-inset">
        {Object.entries(s.answer_titles).map(([key, title]) => (
          <div key={key}>
            <dt className="font-semibold">{title}</dt>
            <dd>
              {s.answers[key] == null
                ? "Not answered"
                : Array.isArray(s.answers[key])
                  ? (s.answers[key] as unknown[]).join(", ")
                  : typeof s.answers[key] === "boolean"
                    ? s.answers[key]
                      ? "Yes"
                      : "No"
                    : String(s.answers[key])}
            </dd>
          </div>
        ))}
      </dl>
      {s.rejection_reason && <p>Rejection reason: {s.rejection_reason}</p>}
      {s.status === "approved" && <p>{s.qc_earned} QC paid</p>}
      {s.status === "pending" && (
        <>
          <p>
            Assess suitability and permission carefully. Automated checks cannot
            prove originality.
          </p>
          <label>
            Rejection reason
            <textarea
              maxLength={1000}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              disabled={busy}
            />
          </label>
          <div className="capture-actions">
            <button
              className="project-button"
              disabled={busy || s.hidden}
              onClick={() => decide("approved")}
            >
              Approve &amp; award QC
            </button>
            <button
              className="project-button secondary"
              disabled={busy}
              onClick={() => decide("rejected")}
            >
              Reject image
            </button>
          </div>
        </>
      )}
      {!s.hidden && !s.image_deleted && (
        <button className="project-link" disabled={busy} onClick={restrict}>
          Hide image &amp; request removal
        </button>
      )}
      <p role="status">{message}</p>
    </article>
  );
}
