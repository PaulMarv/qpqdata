"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import ProjectEditor from "./project-editor";
import { blankDefinition, projectMutation } from "../../lib/projects";
export default function CollectionStart() {
  const [mode, setMode] = useState<"personal" | "crowdsourced" | null>(null);
  const [name, setName] = useState(""),
    [title, setTitle] = useState("Image type"),
    [choices, setChoices] = useState("Round\nSquare\nRectangular\nOther"),
    [licence, setLicence] = useState<"CC0-1.0" | "CC-BY-4.0" | "CC-BY-SA-4.0">(
      "CC0-1.0",
    ),
    [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false);
  const [advanced, setAdvanced] = useState(false);
  const router = useRouter();
  if (advanced) return <ProjectEditor mode="personal" />;
  if (mode === "crowdsourced") return <ProjectEditor />;
  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMessage("");
    const options = choices
      .split("\n")
      .map((x) => x.trim())
      .filter(Boolean);
    if (
      options.length < 2 ||
      options.length > 30 ||
      new Set(options.map((x) => x.toLowerCase())).size !== options.length
    ) {
      setMessage("Use 2–30 distinct label choices, one per line.");
      setBusy(false);
      return;
    }
    try {
      const p = await projectMutation("", "POST", {
        ...blankDefinition(),
        mode: "personal",
        name,
        label_title: title,
        image_count: 500,
        min_width: 1,
        min_height: 1,
        allowed_formats: ["JPEG", "PNG", "WEBP"],
        licence,
        reuse_terms: licence,
        labels: options.map((option, i) => ({
          key: "label_" + i,
          name: option,
          description: "",
        })),
      });
      router.push(`/projects/${p.id}/contribute`);
      router.refresh();
    } catch (e) {
      setMessage(
        e instanceof Error ? e.message : "Collection could not be created.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <main id="main" className="project-shell quick-shell">
      <p className="project-eyebrow">QPQDATA / COLLECTIONS</p>
      <h1>{mode ? "New personal collection" : "What are you collecting?"}</h1>
      <p>
        {mode
          ? "Start collecting in under a minute."
          : "Choose how your dataset will grow."}
      </p>
      {!mode ? (
        <div className="quick-stack">
          <button
            className="project-panel mode-choice"
            onClick={() => setMode("personal")}
          >
            <strong>Collect images myself</strong>
            <span>Private by default · 0 QC</span>
          </button>
          <button
            className="project-panel mode-choice"
            onClick={() => setMode("crowdsourced")}
          >
            <strong>Ask the community</strong>
            <span>Contributors earn QC after approval</span>
          </button>
        </div>
      ) : (
        <form onSubmit={create} className="quick-stack">
          <section className="project-panel">
            <label>
              Collection name
              <input
                required
                maxLength={200}
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Manhole types — Greater Manchester"
              />
            </label>
          </section>
          <section className="project-panel">
            <button
              type="button"
              className="project-link"
              onClick={() => setAdvanced(true)}
            >
              Advanced criteria and optional metadata
            </button>
            <h2>Keep labels simple</h2>
            <p>
              One essential single-choice label keeps capturing fast. Extra
              metadata can stay optional.
            </p>
            <label>
              Required label question
              <input
                required
                maxLength={200}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </label>
            <label>
              One-tap choices · one per line
              <textarea
                required
                value={choices}
                onChange={(e) => setChoices(e.target.value)}
                rows={4}
              />
            </label>
          </section>
          <section className="project-panel">
            <h2>Private · Only you can view or export</h2>
            <p>
              0 QC to create, capture or maintain. Publishing is a separate,
              explicit rights and privacy review and never opens community
              contributions.
            </p>
            <label>
              Recorded image licence
              <select
                value={licence}
                onChange={(e) => setLicence(e.target.value as typeof licence)}
              >
                <option>CC0-1.0</option>
                <option>CC-BY-4.0</option>
                <option>CC-BY-SA-4.0</option>
              </select>
            </label>
            <p>
              Choose terms you have permission to use. These terms and the label
              schema are frozen; public distribution requires additional
              confirmation.
            </p>
          </section>
          {message && <p role="alert">{message}</p>}
          <button className="project-button" disabled={busy}>
            {busy ? "Creating…" : "Create & open camera"}
          </button>
          <button
            type="button"
            className="project-link"
            onClick={() => setMode(null)}
          >
            Back
          </button>
        </form>
      )}
    </main>
  );
}
