import type { components } from "./api-schema";
import type { Definition } from "./projects";
export type Submission = components["schemas"]["SubmissionView"];
export type Answers = Record<string, string | number | boolean | string[]>;
export const maxBytes = 10 * 1024 * 1024;
export function validateLabels(
  d: Definition,
  label: string,
  answers: Answers,
): string | null {
  if (!d.labels?.some((l) => l.key === label)) return "Choose an image label.";
  for (const q of d.criteria?.questions ?? []) {
    const value = answers[q.key];
    const empty =
      value === undefined ||
      value === "" ||
      (Array.isArray(value) && !value.length);
    if (empty) {
      if (q.required) return "Answer: " + q.title;
      continue;
    }
    let valid = false;
    if (q.type === "single_choice")
      valid = typeof value === "string" && (q.options ?? []).includes(value);
    if (q.type === "multiple_choice")
      valid =
        Array.isArray(value) &&
        value.every((v) => (q.options ?? []).includes(v)) &&
        new Set(value).size === value.length &&
        value.length >= (q.min_selections ?? 0) &&
        value.length <= (q.max_selections ?? q.options?.length ?? 0);
    if (q.type === "short_text")
      valid =
        typeof value === "string" &&
        !!value.trim() &&
        value.length >= (q.min_length ?? 0) &&
        value.length <= (q.max_length ?? 2000);
    if (q.type === "number")
      valid =
        typeof value === "number" &&
        Number.isFinite(value) &&
        Math.abs(value) <= 1e15 &&
        (q.min_value == null || value >= q.min_value) &&
        (q.max_value == null || value <= q.max_value) &&
        (!q.integer_only || Number.isInteger(value));
    if (q.type === "yes_no") valid = typeof value === "boolean";
    if (!valid) return "Check the answer: " + q.title;
  }
  return null;
}
export async function submissionAction(
  path: string,
  body: unknown,
): Promise<Submission> {
  const response = await fetch("/api/submissions/" + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const result = await response.json();
  if (!response.ok)
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : "Submission could not be completed.",
    );
  return result as Submission;
}
export function uploadImage(
  id: string,
  file: File,
  onProgress: (percent: number) => void,
  signal?: AbortSignal,
): Promise<Submission> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", "/api/submissions/" + id + "/image");
    xhr.setRequestHeader("Content-Type", "application/octet-stream");
    xhr.timeout = 90000;
    const abort = () => xhr.abort();
    signal?.addEventListener("abort", abort, { once: true });
    const finish = () => signal?.removeEventListener("abort", abort);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable)
        onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      finish();
      try {
        const value = JSON.parse(xhr.responseText);
        if (xhr.status >= 200 && xhr.status < 300) resolve(value as Submission);
        else
          reject(
            new Error(
              typeof value.detail === "string"
                ? value.detail
                : "Image upload failed.",
            ),
          );
      } catch {
        reject(new Error("Image upload failed. Retry safely."));
      }
    };
    xhr.onerror = xhr.ontimeout = () => {
      finish();
      reject(new Error("Connection interrupted. Retry this image safely."));
    };
    xhr.onabort = () => {
      finish();
      reject(new Error("Upload interrupted. Retry uses the same submission."));
    };
    if (signal?.aborted) {
      finish();
      reject(new Error("Upload interrupted."));
      return;
    }
    xhr.send(file);
  });
}
