import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { uploadImage } from "../src/lib/submissions";
class Xhr {
  static instances: Xhr[] = [];
  upload: { onprogress: ((event: ProgressEvent) => void) | null } = {
    onprogress: null,
  };
  onload: (() => void) | null = null;
  onerror: (() => void) | null = null;
  ontimeout: (() => void) | null = null;
  onabort: (() => void) | null = null;
  status = 200;
  responseText = JSON.stringify({ id: "submission", status: "pending" });
  timeout = 0;
  open = vi.fn();
  setRequestHeader = vi.fn();
  send = vi.fn();
  abort = vi.fn(() => this.onabort?.());
  constructor() {
    Xhr.instances.push(this);
  }
}
beforeEach(() => {
  Xhr.instances = [];
  vi.stubGlobal("XMLHttpRequest", Xhr);
});
afterEach(() => vi.unstubAllGlobals());
it("sends raw image bytes on the private path and reports upload progress", async () => {
  const file = new File(["synthetic"], "scene.png", { type: "image/png" }),
    progress = vi.fn();
  const result = uploadImage("submission", file, progress);
  const xhr = Xhr.instances[0];
  expect(xhr.open).toHaveBeenCalledWith(
    "PUT",
    "/api/submissions/submission/image",
  );
  expect(xhr.setRequestHeader).toHaveBeenCalledWith(
    "Content-Type",
    "application/octet-stream",
  );
  expect(xhr.send).toHaveBeenCalledWith(file);
  xhr.upload.onprogress?.({
    lengthComputable: true,
    loaded: 5,
    total: 10,
  } as ProgressEvent);
  expect(progress).toHaveBeenCalledWith(50);
  xhr.onload?.();
  expect(await result).toEqual({ id: "submission", status: "pending" });
});
it("reports backend validation failures and network interruptions for safe retries", async () => {
  const file = new File(["synthetic"], "scene.png");
  const first = uploadImage("submission", file, vi.fn());
  const xhr = Xhr.instances[0];
  xhr.status = 409;
  xhr.responseText = JSON.stringify({ detail: "Collection paused" });
  xhr.onload?.();
  await expect(first).rejects.toThrow("Collection paused");
  const second = uploadImage("submission", file, vi.fn());
  Xhr.instances[1].onerror?.();
  await expect(second).rejects.toThrow("Retry this image safely");
});
it("interrupts the XHR using AbortSignal without creating another submission", async () => {
  const controller = new AbortController();
  const result = uploadImage(
    "same-slot",
    new File(["synthetic"], "scene.png"),
    vi.fn(),
    controller.signal,
  );
  controller.abort();
  expect(Xhr.instances[0].abort).toHaveBeenCalledOnce();
  await expect(result).rejects.toThrow("same submission");
});
