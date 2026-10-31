import type { Definition } from "../../lib/projects";
export default function ProjectDefinition({
  definition: d,
  preview = false,
}: {
  definition: Definition;
  preview?: boolean;
}) {
  return (
    <>
      <section className="project-panel">
        <h2>Collection overview</h2>
        <p>{d.description}</p>
        <h3>Research purpose</h3>
        <p>{d.research_purpose}</p>
        <dl className="project-facts">
          <div>
            <dt>Category</dt>
            <dd>{d.category}</dd>
          </div>
          <div>
            <dt>Images requested</dt>
            <dd>{d.image_count}</dd>
          </div>
          <div>
            <dt>Reward per accepted image</dt>
            <dd>{d.reward_per_image} QC</dd>
          </div>
          <div>
            <dt>Closing date (UTC)</dt>
            <dd>{d.closing_date || "No closing date"}</dd>
          </div>
        </dl>
      </section>
      <section className="project-panel">
        <h2>Photo instructions</h2>
        <p>{d.instructions}</p>
        <h3>Accepted image content</h3>
        <p>{d.accepted_content}</p>
        <h3>Prohibited image content</h3>
        <p>{d.prohibited_content}</p>
        <p>
          Minimum dimensions: {d.min_width} × {d.min_height} pixels. Allowed
          formats: {d.allowed_formats?.join(", ")}.
        </p>
      </section>
      <section className="project-panel">
        <h2>Image labels</h2>
        {d.labels?.length ? (
          d.labels.map((l) => (
            <div className="project-inset" key={l.key}>
              <h3>{l.name}</h3>
              <p>{l.description}</p>
            </div>
          ))
        ) : (
          <p>No labels defined yet.</p>
        )}
      </section>
      <section className="project-panel">
        <h2>Per-image questions</h2>
        <p>
          {preview
            ? "Preview only. Answers are not saved."
            : "These are the questions contributors will answer for each image."}
        </p>
        {d.criteria?.questions?.length ? (
          d.criteria.questions.map((q) => (
            <fieldset className="project-inset" key={q.key}>
              <legend>
                {q.title} · {q.required ? "Required" : "Optional"}
              </legend>
              <p id={q.key + "-help"}>{q.description}</p>
              {q.type === "single_choice" || q.type === "multiple_choice" ? (
                <div>
                  {q.options?.map((o) => (
                    <label className="project-check" key={o}>
                      <input
                        type={q.type === "single_choice" ? "radio" : "checkbox"}
                        name={q.key}
                        disabled={!preview}
                      />
                      {o}
                    </label>
                  ))}
                </div>
              ) : q.type === "yes_no" ? (
                <select
                  aria-label={q.title}
                  disabled={!preview}
                  defaultValue=""
                >
                  <option value="">Choose an answer</option>
                  <option>Yes</option>
                  <option>No</option>
                </select>
              ) : (
                <input
                  aria-label={q.title}
                  aria-describedby={q.key + "-help"}
                  type={q.type === "number" ? "number" : "text"}
                  min={q.min_value ?? undefined}
                  max={q.max_value ?? undefined}
                  step={q.integer_only ? 1 : "any"}
                  minLength={q.min_length ?? undefined}
                  maxLength={q.max_length ?? undefined}
                  disabled={!preview}
                />
              )}
              {q.type === "short_text" && (
                <small>
                  Length: {q.min_length ?? 0}–{q.max_length ?? 2000} characters
                </small>
              )}
              {q.type === "number" && (
                <small>
                  Range: {q.min_value ?? "no minimum"} to{" "}
                  {q.max_value ?? "no maximum"}
                  {q.integer_only ? " · Whole numbers" : ""}
                </small>
              )}
              {q.type === "multiple_choice" && (
                <small>
                  Select {q.min_selections ?? 0}–
                  {q.max_selections ?? q.options?.length} options
                </small>
              )}
            </fieldset>
          ))
        ) : (
          <p>No additional questions.</p>
        )}
      </section>
      <section className="project-panel">
        <h2>Dataset licence &amp; reuse</h2>
        <p>{d.licence || "Licence pending"}</p>
        <p>{d.reuse_terms}</p>
      </section>
    </>
  );
}
