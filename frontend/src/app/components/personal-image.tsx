"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import type { Definition } from "../../lib/projects";
import type { Submission, Answers } from "../../lib/submissions";
import QuickLabels from "./quick-labels";
import SubmissionCard from "./submission-card";
export default function PersonalImage({
  submission: s,
  definition,
  editable,
}: {
  submission: Submission;
  definition: Definition;
  editable: boolean;
}) {
  const [editing, setEditing] = useState(false),
    [label, setLabel] = useState(s.label_key),
    [answers, setAnswers] = useState<Answers>(s.answers as Answers),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const router = useRouter();
  async function save() {
    setBusy(true);
    setError("");
    try {
      const r = await fetch(`/api/submissions/${s.id}/labels`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          label_key: label,
          answers,
          expected_hash: s.annotation_hash,
        }),
      });
      if (!r.ok) {
        const body = await r.json();
        throw new Error(
          typeof body.detail === "string"
            ? body.detail
            : "Labels could not be saved.",
        );
      }
      setEditing(false);
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Save failed.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div>
      <SubmissionCard submission={s} />
      {editable && s.status === "approved" && !s.hidden && (
        <section className="project-panel">
          {!editing ? (
            <button
              className="project-link"
              onClick={() => {
                setLabel(s.label_key);
                setAnswers(s.answers as Answers);
                setEditing(true);
              }}
            >
              Edit labels
            </button>
          ) : (
            <fieldset disabled={busy}>
              <QuickLabels
                definition={definition}
                label={label}
                answers={answers}
                prefix={s.id}
                onLabel={setLabel}
                onAnswer={(key, value) =>
                  setAnswers((old) => {
                    const next = { ...old };
                    if (value === undefined) delete next[key];
                    else next[key] = value;
                    return next;
                  })
                }
              />
              <button className="project-button" onClick={save}>
                Save labels
              </button>
              <button
                className="project-link"
                onClick={() => setEditing(false)}
              >
                Cancel
              </button>
            </fieldset>
          )}
          {error && <p role="alert">{error}</p>}
        </section>
      )}
    </div>
  );
}
