"use client";
/* eslint-disable @next/next/no-img-element -- authenticated/blob previews remain private */
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { Project } from "../../lib/projects";
import {
  maxBytes,
  submissionAction,
  uploadImage,
  validateLabels,
  type Answers,
} from "../../lib/submissions";
import QuickLabels from "./quick-labels";
import ProjectDefinition from "./project-definition";
type Photo = {
  key: string;
  file: File;
  preview: string;
  label: string;
  answers: Answers;
  slot?: string;
};
export default function QuickCapture({
  project: p,
  owner,
}: {
  project: Project;
  owner: boolean;
}) {
  const [photos, setPhotos] = useState<Photo[]>([]),
    [message, setMessage] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [progress, setProgress] = useState(0),
    [camera, setCamera] = useState(false),
    [consent, setConsent] = useState(false),
    [privacy, setPrivacy] = useState(false),
    [saved, setSaved] = useState(0);
  const video = useRef<HTMLVideoElement>(null),
    stream = useRef<MediaStream | null>(null),
    urls = useRef(new Set<string>()),
    abort = useRef<AbortController | null>(null),
    mounted = useRef(true),
    submitting = useRef(false);
  const router = useRouter();
  const photo = photos[0];
  const accepted = (p.definition.allowed_formats ?? [])
    .map(
      (f) => ({ JPEG: "image/jpeg", PNG: "image/png", WEBP: "image/webp" })[f],
    )
    .join(",");
  useEffect(() => {
    mounted.current = true;
    const previews = urls.current;
    return () => {
      mounted.current = false;
      stream.current?.getTracks().forEach((t) => t.stop());
      abort.current?.abort();
      previews.forEach(URL.revokeObjectURL);
    };
  }, []);
  function select(files: File[]) {
    if (!files.length) return;
    if (files.length + photos.length > 5) {
      setError("Choose up to five images at a time.");
      return;
    }
    if (
      files.some(
        (f) =>
          !f.size || f.size > maxBytes || !accepted.split(",").includes(f.type),
      )
    ) {
      setError(
        "Use a supported JPEG, PNG or WebP up to 10 MiB. HEIC must be converted first.",
      );
      return;
    }
    setError("");
    setPhotos((old) => [
      ...old,
      ...files.map((file) => {
        const preview = URL.createObjectURL(file);
        urls.current.add(preview);
        return {
          key: crypto.randomUUID(),
          file,
          preview,
          label: "",
          answers: {},
        };
      }),
    ]);
  }
  function patch(change: Partial<Photo>) {
    setPhotos((old) =>
      old.map((item, i) => (i === 0 ? { ...item, ...change } : item)),
    );
  }
  async function openCamera() {
    setError("");
    if (!navigator.mediaDevices?.getUserMedia) {
      setError(
        "Live camera unavailable. Use Take a photo with device camera or gallery.",
      );
      return;
    }
    try {
      const media = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: "environment" },
          width: { ideal: 1920 },
          height: { ideal: 1080 },
        },
        audio: false,
      });
      if (!mounted.current) {
        media.getTracks().forEach((t) => t.stop());
        return;
      }
      stream.current?.getTracks().forEach((t) => t.stop());
      stream.current = media;
      if (video.current) {
        video.current.srcObject = media;
        await video.current.play();
      }
      setCamera(true);
    } catch {
      stream.current?.getTracks().forEach((t) => t.stop());
      stream.current = null;
      setCamera(false);
      setError(
        "Camera access unavailable. Allow camera permission or choose images from gallery.",
      );
    }
  }
  function takePhoto() {
    const v = video.current;
    if (!v?.videoWidth || !v.videoHeight) {
      setError("Camera is not ready yet.");
      return;
    }
    const canvas = document.createElement("canvas");
    canvas.width = v.videoWidth;
    canvas.height = v.videoHeight;
    canvas.getContext("2d")?.drawImage(v, 0, 0);
    const type = accepted.includes("image/jpeg")
      ? "image/jpeg"
      : accepted.includes("image/png")
        ? "image/png"
        : "image/webp";
    canvas.toBlob(
      (blob) => {
        if (blob && mounted.current)
          select([
            new File(
              [blob],
              "capture." + (type === "image/jpeg" ? "jpg" : "png"),
              { type },
            ),
          ]);
      },
      type,
      0.92,
    );
  }
  function discard() {
    if (!photo) return;
    if (photo.slot) {
      setError(
        "This upload has started. Retry it, or discard its slot from My Submissions before selecting a different image.",
      );
      return;
    }
    URL.revokeObjectURL(photo.preview);
    urls.current.delete(photo.preview);
    setPhotos((old) => old.slice(1));
    setError("");
  }
  async function save(finish: boolean) {
    if (!photo || submitting.current) return;
    const invalid = validateLabels(p.definition, photo.label, photo.answers);
    if (invalid || !consent || !privacy) {
      setError(
        invalid || "Confirm image rights and privacy checks before saving.",
      );
      return;
    }
    submitting.current = true;
    setBusy(true);
    setError("");
    setProgress(0);
    const controller = new AbortController();
    abort.current = controller;
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
      patch({ slot });
      await uploadImage(slot, photo.file, setProgress, controller.signal);
      if (!mounted.current) return;
      URL.revokeObjectURL(photo.preview);
      urls.current.delete(photo.preview);
      setPhotos((old) => old.slice(1));
      setSaved((n) => n + 1);
      setMessage(
        owner
          ? "Saved · 0 QC. Ready for next photo."
          : "Submitted · Pending Review. Ready for next photo.",
      );
      if (finish) {
        router.push(owner ? `/collections/${p.id}/images` : "/submissions");
        router.refresh();
      }
    } catch (e) {
      if (mounted.current)
        setError(
          e instanceof Error ? e.message : "Upload failed. Retry safely.",
        );
    } finally {
      submitting.current = false;
      if (mounted.current) setBusy(false);
      abort.current = null;
    }
  }
  return (
    <main id="main" className="project-shell quick-shell">
      <p className="project-eyebrow">QPQDATA / COLLECTIONS</p>
      <h1>{photo ? "What type is this?" : "Capture, label, repeat"}</h1>
      <p>
        {p.definition.name} ·{" "}
        {owner
          ? "Owner images · 0 QC"
          : `${p.definition.reward_per_image} QC if approved`}{" "}
        · {p.visibility ?? "private"}
      </p>
      <p role="status">{message || `${saved} images saved this session`}</p>
      <aside className="project-notice">
        Avoid faces, number plates, documents and addresses. Submit original
        photos you own or have permission to use. File validation cannot prove
        originality or privacy.
      </aside>
      <details className="project-panel">
        <summary>Collection requirements and reuse terms</summary>
        <ProjectDefinition definition={p.definition} />
      </details>
      <video
        ref={video}
        muted
        playsInline
        className="quick-viewfinder"
        hidden={!camera || !!photo}
        aria-label="Live camera preview"
      />
      {!photo ? (
        <section className="project-panel quick-stack">
          <h2>Camera ready</h2>
          <button
            className="project-button"
            onClick={camera ? takePhoto : openCamera}
          >
            {camera ? "Take photo" : "Open live camera"}
          </button>
          <label className="project-button secondary">
            Take a photo with device camera
            <input
              className="capture-input"
              aria-label="Take a photo with device camera"
              type="file"
              accept={accepted}
              capture="environment"
              onChange={(e) => {
                select(Array.from(e.target.files ?? []));
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
                stream.current?.getTracks().forEach((t) => t.stop());
                stream.current = null;
                setCamera(false);
                select(Array.from(e.target.files ?? []));
                e.target.value = "";
              }}
            />
          </label>
        </section>
      ) : (
        <>
          <section className="project-panel">
            <img
              className="contribution-preview"
              src={photo.preview}
              alt="Current photograph preview"
            />
            <p>
              {photos.length} image{photos.length === 1 ? "" : "s"} to label
            </p>
            <button className="project-link" disabled={busy} onClick={discard}>
              Remove / Retake
            </button>
          </section>
          <fieldset disabled={busy || !!photo.slot} className="quick-stack">
            <QuickLabels
              definition={p.definition}
              prefix={photo.key}
              label={photo.label}
              answers={photo.answers}
              onLabel={(label) => patch({ label })}
              onAnswer={(k, value) => {
                const answers = { ...photo.answers };
                if (value === undefined) delete answers[k];
                else answers[k] = value;
                patch({ answers });
              }}
            />
          </fieldset>
        </>
      )}
      <section className="project-panel">
        <h2>Rights and privacy · this capture session</h2>
        <p>
          {p.definition.licence} · {p.definition.reuse_terms}
        </p>
        <label className="dataset-check">
          <input
            type="checkbox"
            checked={consent}
            onChange={(e) => setConsent(e.target.checked)}
            disabled={busy}
          />
          I own or have permission to submit every image saved in this session
          under the recorded terms.
        </label>
        <label className="dataset-check">
          <input
            type="checkbox"
            checked={privacy}
            onChange={(e) => setPrivacy(e.target.checked)}
            disabled={busy}
          />
          I will check each photo for personal information and third-party
          copyrighted content before saving.
        </label>
      </section>
      {error && (
        <p role="alert" className="project-error">
          {error}
        </p>
      )}
      {busy && (
        <>
          <progress aria-label="Upload progress" value={progress} max={100} />
          <button
            className="project-link"
            onClick={() => abort.current?.abort()}
          >
            Interrupt upload
          </button>
        </>
      )}
      {photo && (
        <div className="quick-stack">
          <button
            className="project-button"
            disabled={busy || !consent || !privacy}
            onClick={() => save(false)}
          >
            {busy
              ? "Saving…"
              : photo.slot
                ? "Retry save & capture next"
                : "Save & Capture Next"}
          </button>
          <button
            className="project-button secondary"
            disabled={busy || !consent || !privacy}
            onClick={() => save(true)}
          >
            Save & Finish
          </button>
        </div>
      )}
      <Link
        className="project-link"
        href={owner ? `/collections/${p.id}/images` : "/submissions"}
      >
        {owner ? "View collection" : "My Submissions"}
      </Link>
      <p>
        Interrupted uploads remain in My Submissions for recovery before their
        15-minute lease expires. Photos are not kept offline.
      </p>
    </main>
  );
}
