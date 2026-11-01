"use client";
import type { Definition } from "../../lib/projects";
import type { Answers } from "../../lib/submissions";
export default function ImageLabels({
  hideLabel = false,
  definition: d,
  prefix,
  label,
  answers,
  onLabel,
  onAnswer,
}: {
  hideLabel?: boolean;
  definition: Definition;
  prefix: string;
  label: string;
  answers: Answers;
  onLabel: (v: string) => void;
  onAnswer: (key: string, value: Answers[string] | undefined) => void;
}) {
  return (
    <div>
      {!hideLabel && (
        <label>
          Image label (required)
          <select
            value={label}
            onChange={(e) => onLabel(e.target.value)}
            required
          >
            <option value="">Choose a label</option>
            {d.labels?.map((l) => (
              <option key={l.key} value={l.key}>
                {l.name}
              </option>
            ))}
          </select>
        </label>
      )}
      {d.labels?.find((l) => l.key === label)?.description && (
        <p>{d.labels.find((l) => l.key === label)?.description}</p>
      )}
      {d.criteria?.questions?.map((q) => {
        const value = answers[q.key],
          id = prefix + "-" + q.key;
        return (
          <fieldset className="project-inset" key={q.key}>
            <legend>
              {q.title} · {q.required ? "Required" : "Optional"}
            </legend>
            {q.description && <p id={id + "-help"}>{q.description}</p>}
            {q.type === "multiple_choice" ? (
              <>
                <p>
                  Select {q.min_selections ?? (q.required ? 1 : 0)}–
                  {q.max_selections ?? q.options?.length} options
                </p>
                {q.options?.map((option) => (
                  <label className="project-check" key={option}>
                    <input
                      type="checkbox"
                      checked={Array.isArray(value) && value.includes(option)}
                      onChange={(e) =>
                        onAnswer(
                          q.key,
                          e.target.checked
                            ? [...(Array.isArray(value) ? value : []), option]
                            : (Array.isArray(value) ? value : []).filter(
                                (x) => x !== option,
                              ),
                        )
                      }
                    />
                    {option}
                  </label>
                ))}
              </>
            ) : q.type === "single_choice" || q.type === "yes_no" ? (
              <select
                id={id}
                aria-label={q.title}
                aria-describedby={q.description ? id + "-help" : undefined}
                required={q.required}
                value={value === undefined ? "" : String(value)}
                onChange={(e) =>
                  onAnswer(
                    q.key,
                    e.target.value === ""
                      ? undefined
                      : q.type === "yes_no"
                        ? e.target.value === "true"
                        : e.target.value,
                  )
                }
              >
                <option value="">Choose an answer</option>
                {q.type === "yes_no" ? (
                  <>
                    <option value="true">Yes</option>
                    <option value="false">No</option>
                  </>
                ) : (
                  q.options?.map((o) => <option key={o}>{o}</option>)
                )}
              </select>
            ) : (
              <input
                id={id}
                aria-label={q.title}
                aria-describedby={q.description ? id + "-help" : undefined}
                type={q.type === "number" ? "number" : "text"}
                required={q.required}
                min={q.min_value ?? undefined}
                max={q.max_value ?? undefined}
                step={q.integer_only ? 1 : "any"}
                minLength={q.min_length ?? undefined}
                maxLength={q.max_length ?? 2000}
                value={value === undefined ? "" : String(value)}
                onChange={(e) =>
                  onAnswer(
                    q.key,
                    e.target.value === ""
                      ? undefined
                      : q.type === "number"
                        ? Number(e.target.value)
                        : e.target.value,
                  )
                }
              />
            )}
            {q.type === "short_text" && (
              <small>
                {q.min_length ?? 0}–{q.max_length ?? 2000} characters
              </small>
            )}
            {q.type === "number" && (
              <small>
                {q.integer_only ? "Whole numbers. " : ""}Minimum{" "}
                {q.min_value ?? "not set"}; maximum {q.max_value ?? "not set"}.
              </small>
            )}
          </fieldset>
        );
      })}
    </div>
  );
}
