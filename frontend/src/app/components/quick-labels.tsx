"use client";
import type { Definition } from "../../lib/projects";
import type { Answers } from "../../lib/submissions";
import ImageLabels from "./image-labels";
export default function QuickLabels({
  definition: d,
  label,
  answers,
  onLabel,
  onAnswer,
  prefix,
}: {
  definition: Definition;
  label: string;
  answers: Answers;
  onLabel: (v: string) => void;
  onAnswer: (k: string, v: Answers[string] | undefined) => void;
  prefix: string;
}) {
  const questions = d.criteria?.questions ?? [];
  const required = questions.filter((q) => q.required),
    optional = questions.filter((q) => !q.required);
  const fields = (qs: typeof questions) => (
    <ImageLabels
      definition={{
        ...d,
        labels: [],
        criteria: { schema_version: 1, questions: qs },
      }}
      prefix={prefix}
      label={label}
      answers={answers}
      onLabel={onLabel}
      onAnswer={onAnswer}
      hideLabel
    />
  );
  return (
    <>
      <fieldset className="project-panel">
        <legend>
          {d.label_title || "Image label"} · Select one (required)
        </legend>
        <div className="quick-choices">
          {d.labels?.map((l) => (
            <button
              type="button"
              key={l.key}
              aria-pressed={label === l.key}
              className={"quick-choice" + (label === l.key ? " selected" : "")}
              onClick={() => onLabel(l.key)}
            >
              {l.name}
            </button>
          ))}
        </div>
      </fieldset>
      {required.length > 0 && (
        <section className="project-panel">
          <h2>Required collection details</h2>
          {fields(required)}
        </section>
      )}
      {optional.length > 0 && (
        <details className="project-panel">
          <summary>More details (optional)</summary>
          {fields(optional)}
        </details>
      )}
    </>
  );
}
