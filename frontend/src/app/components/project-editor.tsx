"use client";
import Link from "next/link";
import { useState, type FormEvent, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import {
  blankDefinition,
  budget,
  categories,
  key,
  projectMutation,
  type Definition,
  type Project,
  type Question,
} from "../../lib/projects";
import ProjectDefinition from "./project-definition";
function Field({ title, children }: { title: string; children: ReactNode }) {
  return (
    <label>
      {title}
      {children}
    </label>
  );
}
export default function ProjectEditor({ initial }: { initial?: Project }) {
  const [d, setD] = useState<Definition>(
    initial?.definition ?? blankDefinition,
  );
  const [preview, setPreview] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const router = useRouter();
  function update<K extends keyof Definition>(name: K, value: Definition[K]) {
    setD((old) => ({ ...old, [name]: value }));
  }
  const questions = d.criteria?.questions ?? [],
    labels = d.labels ?? [];
  function setQuestions(q: Question[]) {
    update("criteria", { schema_version: 1, questions: q });
  }
  function question(i: number, patch: Partial<Question>) {
    setQuestions(questions.map((q, n) => (n === i ? { ...q, ...patch } : q)));
  }
  async function save(event: FormEvent) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      const p = await projectMutation(
        initial ? "/" + initial.id : "",
        initial ? "PUT" : "POST",
        initial ? { expected_version: initial.version, definition: d } : d,
      );
      router.push("/projects/" + p.id);
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unable to save draft.");
    } finally {
      setBusy(false);
    }
  }
  const text = (
    name:
      | "description"
      | "research_purpose"
      | "instructions"
      | "accepted_content"
      | "prohibited_content"
      | "reuse_terms",
    title: string,
  ) => (
    <Field title={title}>
      <textarea
        rows={3}
        maxLength={5000}
        value={d[name] ?? ""}
        onChange={(e) => update(name, e.target.value)}
      />
    </Field>
  );
  const numeric = (
    name: "image_count" | "reward_per_image" | "min_width" | "min_height",
    title: string,
    max: number,
  ) => (
    <Field title={title}>
      <input
        type="number"
        min={1}
        max={max}
        step={1}
        required
        value={d[name] ?? ""}
        onChange={(e) => update(name, Number(e.target.value))}
      />
    </Field>
  );
  return (
    <main id="main" className="project-shell">
      <Link className="project-link" href="/collections">
        ← My Collections
      </Link>
      <div className="project-heading">
        <div>
          <p className="project-eyebrow">Collection builder</p>
          <h1>
            {preview
              ? "Preview your collection"
              : "Define contribution requirements"}
          </h1>
          <p>Create clear image labels and questions for contributors.</p>
        </div>
        <button
          type="button"
          className="project-button secondary"
          onClick={() => setPreview(!preview)}
        >
          {preview ? "Back to editor" : "Preview draft"}
        </button>
      </div>
      {preview ? (
        <>
          <p className="project-notice">
            Unsaved preview · {d.name || "Untitled collection"} · {budget(d)} QC
            budget. Answers are not saved.
          </p>
          <ProjectDefinition definition={d} preview />
        </>
      ) : (
        <form onSubmit={save}>
          <section className="project-panel">
            <h2>Dataset details</h2>
            <div className="project-grid">
              <Field title="Project name (required)">
                <input
                  required
                  maxLength={200}
                  value={d.name}
                  onChange={(e) => update("name", e.target.value)}
                />
              </Field>
              <Field title="Project ID (automatic)">
                <input
                  readOnly
                  value={initial?.id ?? "Generated when you save your draft"}
                />
              </Field>
            </div>
            {text("description", "Description")}
            {text("research_purpose", "Research purpose")}
            <div className="project-grid">
              <Field title="Category">
                <select
                  value={d.category}
                  onChange={(e) =>
                    update("category", e.target.value as Definition["category"])
                  }
                >
                  {categories.map((c) => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
              </Field>
              <Field title="Keywords (comma separated, up to 20)">
                <input
                  maxLength={1000}
                  value={d.keywords?.join(",") ?? ""}
                  onChange={(e) =>
                    update("keywords", e.target.value.split(","))
                  }
                  onBlur={() =>
                    update(
                      "keywords",
                      d.keywords?.map((x) => x.trim()).filter(Boolean),
                    )
                  }
                />
              </Field>
            </div>
          </section>
          <section className="project-panel">
            <h2>Collection instructions &amp; content</h2>
            {text("instructions", "Collection instructions")}
            {text("accepted_content", "Accepted image content")}
            {text("prohibited_content", "Prohibited image content")}
            <div className="project-grid">
              {numeric("min_width", "Minimum width (pixels)", 20000)}
              {numeric("min_height", "Minimum height (pixels)", 20000)}
            </div>
            <fieldset>
              <legend>Allowed image formats (choose at least one)</legend>
              <div className="project-actions">
                {(["JPEG", "PNG", "WEBP"] as const).map((f) => (
                  <label className="project-check" key={f}>
                    <input
                      type="checkbox"
                      checked={d.allowed_formats?.includes(f) ?? false}
                      onChange={(e) =>
                        update(
                          "allowed_formats",
                          e.target.checked
                            ? [...(d.allowed_formats ?? []), f]
                            : (d.allowed_formats ?? []).filter((x) => x !== f),
                        )
                      }
                    />
                    {f}
                  </label>
                ))}
              </div>
            </fieldset>
          </section>
          <section className="project-panel">
            <h2>Required image labels</h2>
            <p>
              Define the classes this dataset uses. At least one label is
              required before publication.
            </p>
            {labels.map((l, i) => (
              <div className="project-inset" key={l.key}>
                <Field title={"Label " + (i + 1) + " name"}>
                  <input
                    required
                    maxLength={200}
                    value={l.name}
                    onChange={(e) =>
                      update(
                        "labels",
                        labels.map((x, n) =>
                          n === i ? { ...x, name: e.target.value } : x,
                        ),
                      )
                    }
                  />
                </Field>
                <Field title={"Label " + (i + 1) + " description"}>
                  <textarea
                    maxLength={2000}
                    value={l.description ?? ""}
                    onChange={(e) =>
                      update(
                        "labels",
                        labels.map((x, n) =>
                          n === i ? { ...x, description: e.target.value } : x,
                        ),
                      )
                    }
                  />
                </Field>
                <button
                  type="button"
                  className="project-link"
                  onClick={() =>
                    update(
                      "labels",
                      labels.filter((_, n) => n !== i),
                    )
                  }
                >
                  Remove label {i + 1}
                </button>
              </div>
            ))}
            <button
              type="button"
              className="project-button secondary"
              disabled={labels.length >= 30}
              onClick={() =>
                update("labels", [
                  ...labels,
                  { key: key("label"), name: "", description: "" },
                ])
              }
            >
              + Add label
            </button>
          </section>
          <section className="project-panel">
            <h2>Per-image questions</h2>
            <p>
              Choose the metadata contributors will supply. Add up to 30
              questions.
            </p>
            {questions.map((q, i) => (
              <fieldset className="project-inset" key={q.key}>
                <legend>Question {i + 1}</legend>
                <div className="project-grid">
                  <Field title="Field type">
                    <select
                      value={q.type}
                      onChange={(e) => {
                        const type = e.target.value as Question["type"];
                        setQuestions(
                          questions.map((old, n) =>
                            n === i
                              ? {
                                  key: old.key,
                                  title: old.title,
                                  description: old.description,
                                  required: old.required,
                                  integer_only: false,
                                  type,
                                  options:
                                    type === "single_choice" ||
                                    type === "multiple_choice"
                                      ? ["Option 1", "Option 2"]
                                      : [],
                                }
                              : old,
                          ),
                        );
                      }}
                    >
                      {[
                        ["single_choice", "Single choice"],
                        ["multiple_choice", "Multiple choice"],
                        ["short_text", "Short text"],
                        ["number", "Number"],
                        ["yes_no", "Yes / No"],
                      ].map(([v, t]) => (
                        <option key={v} value={v}>
                          {t}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <Field title="Question title">
                    <input
                      required
                      maxLength={200}
                      value={q.title}
                      onChange={(e) => question(i, { title: e.target.value })}
                    />
                  </Field>
                </div>
                <Field title="Question description">
                  <textarea
                    maxLength={2000}
                    value={q.description ?? ""}
                    onChange={(e) =>
                      question(i, { description: e.target.value })
                    }
                  />
                </Field>
                <label className="project-check">
                  <input
                    type="checkbox"
                    checked={q.required ?? false}
                    onChange={(e) =>
                      question(i, { required: e.target.checked })
                    }
                  />
                  Required answer
                </label>
                {(q.type === "single_choice" ||
                  q.type === "multiple_choice") && (
                  <div>
                    <h3>Answer options</h3>
                    {q.options?.map((o, j) => (
                      <div className="project-option" key={j}>
                        <label className="project-grow">
                          Option {j + 1}
                          <input
                            required
                            maxLength={200}
                            value={o}
                            onChange={(e) =>
                              question(i, {
                                options: q.options?.map((x, n) =>
                                  n === j ? e.target.value : x,
                                ),
                              })
                            }
                          />
                        </label>
                        <button
                          type="button"
                          aria-label={"Remove option " + (j + 1)}
                          disabled={(q.options?.length ?? 0) <= 2}
                          onClick={() =>
                            question(i, {
                              options: q.options?.filter((_, n) => n !== j),
                            })
                          }
                        >
                          Remove
                        </button>
                      </div>
                    ))}
                    <button
                      type="button"
                      className="project-link"
                      disabled={(q.options?.length ?? 0) >= 30}
                      onClick={() =>
                        question(i, { options: [...(q.options ?? []), ""] })
                      }
                    >
                      + Add option
                    </button>
                  </div>
                )}
                {(q.type === "short_text" ||
                  q.type === "number" ||
                  q.type === "multiple_choice") && (
                  <div className="project-grid">
                    {(q.type === "short_text"
                      ? ["min_length", "max_length"]
                      : q.type === "number"
                        ? ["min_value", "max_value"]
                        : ["min_selections", "max_selections"]
                    ).map((rule) => {
                      const k = rule as
                        | "min_length"
                        | "max_length"
                        | "min_value"
                        | "max_value"
                        | "min_selections"
                        | "max_selections";
                      return (
                        <Field key={k} title={k.replaceAll("_", " ")}>
                          <input
                            type="number"
                            step={
                              q.type === "number" && !q.integer_only ? "any" : 1
                            }
                            min={
                              q.type === "number"
                                ? undefined
                                : k.startsWith("max")
                                  ? 1
                                  : 0
                            }
                            max={
                              q.type === "short_text"
                                ? 2000
                                : q.type === "multiple_choice"
                                  ? q.options?.length
                                  : undefined
                            }
                            value={q[k] ?? ""}
                            onChange={(e) =>
                              question(i, {
                                [k]:
                                  e.target.value === ""
                                    ? null
                                    : Number(e.target.value),
                              })
                            }
                          />
                        </Field>
                      );
                    })}
                  </div>
                )}
                {q.type === "number" && (
                  <label className="project-check">
                    <input
                      type="checkbox"
                      checked={q.integer_only ?? false}
                      onChange={(e) =>
                        question(i, { integer_only: e.target.checked })
                      }
                    />
                    Whole numbers only
                  </label>
                )}
                <div className="project-actions">
                  <button
                    type="button"
                    className="project-link"
                    disabled={i === 0}
                    onClick={() => {
                      const copy = [...questions];
                      [copy[i - 1], copy[i]] = [copy[i], copy[i - 1]];
                      setQuestions(copy);
                    }}
                  >
                    Move up
                  </button>
                  <button
                    type="button"
                    className="project-link"
                    disabled={i === questions.length - 1}
                    onClick={() => {
                      const copy = [...questions];
                      [copy[i + 1], copy[i]] = [copy[i], copy[i + 1]];
                      setQuestions(copy);
                    }}
                  >
                    Move down
                  </button>
                  <button
                    type="button"
                    className="project-link"
                    onClick={() =>
                      setQuestions(questions.filter((_, n) => n !== i))
                    }
                  >
                    Remove question {i + 1}
                  </button>
                </div>
              </fieldset>
            ))}
            <button
              type="button"
              className="project-button secondary"
              disabled={questions.length >= 30}
              onClick={() =>
                setQuestions([
                  ...questions,
                  {
                    key: key("field"),
                    title: "",
                    description: "",
                    type: "single_choice",
                    required: true,
                    integer_only: false,
                    options: ["Option 1", "Option 2"],
                  },
                ])
              }
            >
              + Add question
            </button>
          </section>
          <section className="project-panel">
            <h2>Budget, schedule &amp; licence</h2>
            <div className="project-grid">
              {numeric("image_count", "Number of images requested", 1000000)}
              {numeric(
                "reward_per_image",
                "Reward per accepted image (QC)",
                1000,
              )}
              <Field title="Optional closing date (UTC)">
                <input
                  type="date"
                  value={d.closing_date ?? ""}
                  onChange={(e) =>
                    update("closing_date", e.target.value || null)
                  }
                />
              </Field>
              <Field title="Dataset licence">
                <select
                  value={d.licence}
                  onChange={(e) =>
                    update("licence", e.target.value as Definition["licence"])
                  }
                >
                  <option value="">Choose a licence</option>
                  <option value="CC0-1.0">CC0 1.0</option>
                  <option value="CC-BY-4.0">CC BY 4.0</option>
                  <option value="CC-BY-SA-4.0">CC BY-SA 4.0</option>
                  <option value="custom">Custom (describe below)</option>
                </select>
              </Field>
            </div>
            {text("reuse_terms", "Intended reuse terms")}
            <p className="project-notice">
              Reservation required on publication:{" "}
              <strong>{budget(d)} QC</strong>. Saving a draft reserves no
              credits.
            </p>
          </section>
          <aside className="project-notice">
            Before publishing, complete the purpose, instructions, content
            rules, labels, licence and reuse terms. Published definitions are
            frozen; changed criteria require a new collection.
          </aside>
          {error && (
            <p role="alert" className="project-error">
              {error}
            </p>
          )}
          <div className="project-actions">
            <button className="project-button" disabled={busy}>
              {busy ? "Saving…" : "Save draft"}
            </button>
            <button
              type="button"
              className="project-button secondary"
              onClick={() => setPreview(true)}
            >
              Preview draft
            </button>
            <Link href="/collections" className="project-link">
              Cancel
            </Link>
          </div>
        </form>
      )}
    </main>
  );
}
