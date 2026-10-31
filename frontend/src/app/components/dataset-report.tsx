"use client";
import { useState } from "react";
import { datasetAction } from "../../lib/datasets";
export default function DatasetReport({ id }: { id: string }) {
  const [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false);
  return (
    <section className="project-panel">
      <h2>Privacy and removal concerns</h2>
      <p>
        Report an image or licence concern for owner review. Do not include
        sensitive documents or account credentials. A report is reviewed; it
        does not automatically establish a violation.
      </p>
      <form
        className="project-form"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          const form = new FormData(e.currentTarget);
          try {
            await datasetAction(`${id}/reports`, {
              image_id: String(form.get("image_id") || "") || null,
              reason: String(form.get("reason")),
              details: String(form.get("details")),
            });
            setMessage("Report recorded for owner review.");
          } catch (error) {
            setMessage(
              error instanceof Error ? error.message : "Report failed.",
            );
          } finally {
            setBusy(false);
          }
        }}
      >
        <label>
          Image identifier (optional, from manifest)
          <input name="image_id" pattern="[0-9a-fA-F-]{36}" />
        </label>
        <label>
          Concern
          <select name="reason">
            <option value="privacy">Privacy</option>
            <option value="copyright">Copyright</option>
            <option value="licence">Licence</option>
            <option value="other">Other</option>
          </select>
        </label>
        <label>
          Details
          <textarea name="details" required maxLength={1000} />
        </label>
        <button className="project-button secondary" disabled={busy}>
          Send report
        </button>
      </form>
      <p role="status">{message}</p>
    </section>
  );
}
