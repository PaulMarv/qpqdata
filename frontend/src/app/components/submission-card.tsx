"use client";
/* eslint-disable @next/next/no-img-element -- authenticated private images must not use a public optimiser */
import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  maxBytes,
  submissionAction,
  uploadImage,
  type Submission,
} from "../../lib/submissions";
export default function SubmissionCard({
  submission: s,
}: {
  submission: Submission;
}) {
  const [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false),
    [progress, setProgress] = useState(0),
    [report, setReport] = useState(false);
  const router = useRouter();
  async function recover(file: File | undefined) {
    if (!file) return;
    if (file.size > maxBytes) {
      setMessage("Image exceeds 10 MiB.");
      return;
    }
    setBusy(true);
    setMessage("");
    try {
      await uploadImage(s.id, file, setProgress);
      setMessage("Submitted · Pending Review");
      router.refresh();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Retry failed.");
    } finally {
      setBusy(false);
    }
  }
  async function action(
    kind: "cancel" | "removal-request",
    reason = "privacy",
    details = "",
  ) {
    setBusy(true);
    setMessage("");
    try {
      await submissionAction(
        s.id + "/" + kind,
        kind === "cancel" ? {} : { reason, details },
      );
      setMessage(
        kind === "cancel"
          ? "Upload discarded."
          : "Removal request recorded. Image access is hidden pending review.",
      );
      setReport(false);
      router.refresh();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Request failed.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <article className="project-panel">
      <div className="project-result-top">
        <Link href={"/projects/" + s.project_id} className="project-link">
          {s.project_name}
        </Link>
        <span className="project-tag">
          {s.expired
            ? "Expired upload"
            : s.status === "pending"
              ? "Pending Review"
              : s.status}
        </span>
      </div>
      <p className="project-id">
        Submission {s.id} · Definition v{s.criteria_version}
      </p>
      {s.status === "pending" && !s.hidden && (
        <img
          className="contribution-preview"
          src={"/api/submissions/" + s.id + "/image"}
          alt={"Your submission to " + s.project_name}
        />
      )}
      <p>
        Label: {s.label_name} ·{" "}
        {new Date(s.created_at).toLocaleDateString("en-GB", {
          timeZone: "UTC",
        })}
      </p>
      <p>
        {s.width
          ? `${s.width} × ${s.height} pixels · ${s.image_format}`
          : "Upload not completed"}
      </p>
      <details>
        <summary>Submitted answers and consent</summary>
        <dl className="project-inset">
          {Object.entries(s.answer_titles).map(([key, title]) => {
            const value = s.answers[key];
            return (
              <div key={key}>
                <dt className="font-semibold">{title}</dt>
                <dd>
                  {value == null || value === ""
                    ? "Not answered"
                    : Array.isArray(value)
                      ? value.join(", ")
                      : typeof value === "boolean"
                        ? value
                          ? "Yes"
                          : "No"
                        : String(value)}
                </dd>
              </div>
            );
          })}
        </dl>
        <p>{s.consent_record.statement as string}</p>
        <p>
          {s.consent_record.licence as string} ·{" "}
          {s.consent_record.reuse_terms as string}
        </p>
      </details>
      {s.hidden ? (
        <p>Image access hidden · removal request awaiting review.</p>
      ) : s.status === "uploading" && !s.expired ? (
        <div className="capture-actions">
          <label className="project-button secondary">
            Retry image upload
            <input
              className="capture-input"
              aria-label="Retry image upload"
              disabled={busy}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={(e) => recover(e.target.files?.[0])}
            />
          </label>
          <button
            className="project-link"
            disabled={busy}
            onClick={() => action("cancel")}
          >
            Discard unfinished upload
          </button>
          {busy && (
            <progress
              aria-label="Recovery upload progress"
              value={progress}
              max={100}
            />
          )}
        </div>
      ) : (
        s.status === "pending" && (
          <button
            className="project-link"
            disabled={busy}
            onClick={() => setReport(!report)}
          >
            Report a concern / request removal
          </button>
        )
      )}
      {report && (
        <form
          className="project-inset"
          onSubmit={(e) => {
            e.preventDefault();
            const data = new FormData(e.currentTarget);
            action(
              "removal-request",
              String(data.get("reason")),
              String(data.get("details")),
            );
          }}
        >
          <label>
            Reason
            <select name="reason">
              <option value="privacy">Privacy</option>
              <option value="copyright">Copyright or permission</option>
              <option value="other">Other</option>
            </select>
          </label>
          <label>
            Details (optional)
            <textarea name="details" maxLength={1000} />
          </label>
          <button className="project-button" disabled={busy}>
            Send removal request &amp; hide image
          </button>
        </form>
      )}
      <p role="status">{message}</p>
    </article>
  );
}
