"use client";
/* eslint-disable @next/next/no-img-element -- private/blob previews cannot use a public image optimiser */
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import type { Project } from "../../lib/projects";
import {
  maxBytes,
  submissionAction,
  uploadImage,
  validateLabels,
  type Answers,
} from "../../lib/submissions";
import ProjectDefinition from "./project-definition";
import ImageLabels from "./image-labels";
type Photo = {
  key: string;
  file: File;
  preview: string;
  label: string;
  answers: Answers;
  slot?: string;
  status: "ready" | "uploading" | "done" | "error";
  progress: number;
  error?: string;
};
export default function Contributor({ project: p }: { project: Project }) {
  const [step, setStep] = useState<
    "requirements" | "select" | "review" | "result"
  >("requirements");
  const [photos, setPhotos] = useState<Photo[]>([]),
    [error, setError] = useState(""),
    [consent, setConsent] = useState(false),
    [privacy, setPrivacy] = useState(false),
    [busy, setBusy] = useState(false);
  const urls = useRef(new Set<string>()),
    abort = useRef<AbortController | null>(null);
  useEffect(() => {
    const saved = urls.current;
    return () => {
      for (const url of saved) URL.revokeObjectURL(url);
      abort.current?.abort();
    };
  }, []);
  function patch(key: string, change: Partial<Photo>) {
    setPhotos((old) =>
      old.map((x) => (x.key === key ? { ...x, ...change } : x)),
    );
  }
  function select(files: FileList | null, replace?: string) {
    if (!files || files.length === 0) return;
    setError("");
    const selected = Array.from(files);
    if (!replace && selected.length + photos.length > 5) {
      setError("Select up to five images per batch.");
      return;
    }
    const allowed = (p.definition.allowed_formats ?? []).map(
      (f) => ({ JPEG: "image/jpeg", PNG: "image/png", WEBP: "image/webp" })[f],
    );
    if (selected.some((f) => !allowed.includes(f.type))) {
      setError(
        "Choose a supported JPEG, PNG or WebP image. HEIC is not supported; export it as JPEG first.",
      );
      return;
    }
    if (selected.some((f) => f.size > maxBytes || f.size === 0)) {
      setError("Each image must be nonempty and no larger than 10 MiB.");
      return;
    }
    const newPhotos = selected.map((file) => {
      const preview = URL.createObjectURL(file);
      urls.current.add(preview);
      return {
        key: crypto.randomUUID(),
        file,
        preview,
        label: "",
        answers: {},
        status: "ready" as const,
        progress: 0,
      };
    });
    if (replace) {
      const old = photos.find((x) => x.key === replace);
      if (old) {
        URL.revokeObjectURL(old.preview);
        urls.current.delete(old.preview);
      }
      setPhotos((current) =>
        current.map((x) => (x.key === replace ? newPhotos[0] : x)),
      );
    } else setPhotos((current) => [...current, ...newPhotos]);
  }
  function remove(photo: Photo) {
    URL.revokeObjectURL(photo.preview);
    urls.current.delete(photo.preview);
    setPhotos((old) => old.filter((x) => x.key !== photo.key));
  }
  function review() {
    for (const photo of photos) {
      const invalid = validateLabels(p.definition, photo.label, photo.answers);
      if (invalid) {
        setError(photo.file.name + ": " + invalid);
        return;
      }
    }
    if (!photos.length) {
      setError("Select at least one image.");
      return;
    }
    setError("");
    setStep("review");
  }
  async function submit() {
    if (!consent || !privacy) return;
    setBusy(true);
    setError("");
    setStep("result");
    for (const photo of photos.filter((x) => x.status !== "done")) {
      const controller = new AbortController();
      abort.current = controller;
      patch(photo.key, { status: "uploading", progress: 0, error: undefined });
      try {
        const slot =
          photo.slot ??
          (
            await submissionAction("start/" + p.id, {
              request_key: photo.key,
              criteria_version: p.published_version,
              label_key: photo.label,
              answers: photo.answers,
              consent: true,
              privacy_acknowledgement: true,
            })
          ).id;
        patch(photo.key, { slot });
        await uploadImage(
          slot,
          photo.file,
          (progress) => patch(photo.key, { progress }),
          controller.signal,
        );
        patch(photo.key, { status: "done", progress: 100 });
      } catch (e) {
        patch(photo.key, {
          status: "error",
          error:
            e instanceof Error ? e.message : "Upload failed. Retry safely.",
        });
      }
    }
    abort.current = null;
    setBusy(false);
  }
  const accepted = (p.definition.allowed_formats ?? [])
    .map(
      (f) => ({ JPEG: "image/jpeg", PNG: "image/png", WEBP: "image/webp" })[f],
    )
    .join(",");
  return (
    <main id="main" className="project-shell">
      <Link href={"/projects/" + p.id} className="project-link">
        ← Collection
      </Link>
      <div className="project-heading">
        <div>
          <p className="project-eyebrow">
            Contribute · published definition v{p.published_version}
          </p>
          <h1>{p.definition.name}</h1>
          <p>
            {step === "requirements"
              ? "1. Read the collection requirements"
              : step === "select"
                ? "2. Select, preview and label each image"
                : step === "review"
                  ? "3. Review and confirm"
                  : "4. Upload results"}
          </p>
        </div>
      </div>
      {step === "requirements" ? (
        <>
          <aside className="project-notice">
            Only submit photographs you own or have permission to share. Avoid
            identifiable faces, personal documents, addresses and copyrighted
            third-party images. Metadata is removed, but visible personal
            information is not automatically detected. File checks do not prove
            originality.
          </aside>
          <ProjectDefinition definition={p.definition} />
          <section className="project-panel">
            <p>
              Up to 5 images per batch, 10 MiB and 24 megapixels per image.
              Maximum 20 images per contributor per collection. Upload slots
              expire after 15 minutes. Pending images count toward collection
              capacity.
            </p>
            <button
              className="project-button"
              onClick={() => setStep("select")}
            >
              Continue to image selection
            </button>
          </section>
        </>
      ) : step === "select" ? (
        <>
          <section className="project-panel">
            <h2>Camera or gallery</h2>
            <p>
              Gallery selection does not request camera access. Camera capture
              uses your device’s supported picker; some browsers offer a file
              picker instead.
            </p>
            <div className="capture-actions">
              <label className="project-button">
                Take a photo
                <input
                  className="capture-input"
                  aria-label="Take a photo"
                  type="file"
                  accept={accepted}
                  capture="environment"
                  onChange={(e) => {
                    select(e.target.files);
                    e.target.value = "";
                  }}
                />
              </label>
              <label className="project-button secondary">
                Choose from gallery
                <input
                  className="capture-input"
                  aria-label="Choose from gallery"
                  type="file"
                  accept={accepted}
                  multiple
                  onChange={(e) => {
                    select(e.target.files);
                    e.target.value = "";
                  }}
                />
              </label>
            </div>
            <p>{photos.length} of 5 images selected</p>
          </section>
          {photos.map((photo, i) => (
            <section className="project-panel" key={photo.key}>
              <h2>
                Image {i + 1} · {photo.file.name}
              </h2>
              <img
                className="contribution-preview"
                src={photo.preview}
                alt={"Preview of image " + (i + 1)}
              />
              <div className="capture-actions">
                <button className="project-link" onClick={() => remove(photo)}>
                  Remove image {i + 1}
                </button>
                <label className="project-link">
                  Replace
                  <input
                    className="capture-input"
                    aria-label={"Replace image " + (i + 1)}
                    type="file"
                    accept={accepted}
                    onChange={(e) => select(e.target.files, photo.key)}
                  />
                </label>
                <label className="project-link">
                  Retake
                  <input
                    className="capture-input"
                    aria-label={"Retake image " + (i + 1)}
                    type="file"
                    accept={accepted}
                    capture="environment"
                    onChange={(e) => select(e.target.files, photo.key)}
                  />
                </label>
              </div>
              <ImageLabels
                definition={p.definition}
                prefix={photo.key}
                label={photo.label}
                answers={photo.answers}
                onLabel={(label) => patch(photo.key, { label })}
                onAnswer={(key, value) => {
                  const answers = { ...photo.answers };
                  if (value === undefined) delete answers[key];
                  else answers[key] = value;
                  patch(photo.key, { answers });
                }}
              />
            </section>
          ))}
          {error && (
            <p role="alert" className="project-error">
              {error}
            </p>
          )}
          <div className="project-actions">
            <button className="project-button" onClick={review}>
              Review {photos.length} images
            </button>
            <button
              className="project-link"
              onClick={() => setStep("requirements")}
            >
              Back to requirements
            </button>
          </div>
        </>
      ) : step === "review" ? (
        <>
          <section className="project-panel">
            <h2>Review your images</h2>
            {photos.map((photo, i) => (
              <article
                className="submission-review project-inset"
                key={photo.key}
              >
                <img src={photo.preview} alt={"Review image " + (i + 1)} />
                <div>
                  <h3>
                    Image {i + 1}: {photo.file.name}
                  </h3>
                  <p>
                    {
                      p.definition.labels?.find((l) => l.key === photo.label)
                        ?.name
                    }
                  </p>
                  {p.definition.criteria?.questions?.map((q) => (
                    <p key={q.key}>
                      {q.title}:{" "}
                      {photo.answers[q.key] === undefined
                        ? "Not answered"
                        : Array.isArray(photo.answers[q.key])
                          ? (photo.answers[q.key] as string[]).join(", ")
                          : typeof photo.answers[q.key] === "boolean"
                            ? photo.answers[q.key]
                              ? "Yes"
                              : "No"
                            : String(photo.answers[q.key])}
                    </p>
                  ))}
                </div>
              </article>
            ))}
          </section>
          <section className="project-panel">
            <h2>Licence &amp; permission</h2>
            <p>{p.definition.licence}</p>
            <p>{p.definition.reuse_terms}</p>
            <label className="project-check">
              <input
                type="checkbox"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
              />
              I own or have permission to submit these images and agree to this
              collection’s licence and reuse terms.
            </label>
            <label className="project-check">
              <input
                type="checkbox"
                checked={privacy}
                onChange={(e) => setPrivacy(e.target.checked)}
              />
              I have checked for faces, personal documents, addresses and
              third-party copyrighted content.
            </label>
            <div className="project-actions">
              <button
                className="project-button"
                disabled={!consent || !privacy}
                onClick={submit}
              >
                Submit {photos.length} images
              </button>
              <button
                className="project-link"
                onClick={() => setStep("select")}
              >
                Back to labelling
              </button>
            </div>
          </section>
        </>
      ) : (
        <>
          <section className="project-panel">
            <h2>{busy ? "Uploading your images" : "Submission results"}</h2>
            <div aria-live="polite">
              {photos.map((photo, i) => (
                <article key={photo.key} className="project-inset">
                  <h3>
                    Image {i + 1} · {photo.file.name}
                  </h3>
                  {photo.status === "uploading" ? (
                    <>
                      <progress
                        aria-label={"Upload progress for image " + (i + 1)}
                        max={100}
                        value={photo.progress}
                      />
                      <p>
                        {photo.progress === 100
                          ? "Validating and saving…"
                          : photo.progress + "% uploaded"}
                      </p>
                      <button
                        className="project-link"
                        onClick={() => abort.current?.abort()}
                      >
                        Interrupt current upload
                      </button>
                    </>
                  ) : photo.status === "done" ? (
                    <p>
                      Submitted · Pending Review. No credits have been paid.
                    </p>
                  ) : photo.status === "error" ? (
                    <p className="project-error">{photo.error}</p>
                  ) : (
                    <p>Waiting to upload</p>
                  )}
                </article>
              ))}
            </div>
            {!busy && photos.some((p) => p.status === "error") && (
              <button className="project-button" onClick={submit}>
                Retry failed images
              </button>
            )}
            <div className="project-actions">
              <Link href="/submissions" className="project-link">
                My Submissions
              </Link>
              {!busy && (
                <Link href={"/projects/" + p.id} className="project-link">
                  Back to collection
                </Link>
              )}
            </div>
            <p>
              You can request removal from My Submissions. If an upload was
              interrupted, retrying will not create a duplicate submission.
              Unfinished uploads can be recovered or discarded there before
              their 15-minute lease expires.
            </p>
          </section>
        </>
      )}
    </main>
  );
}
