import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import QuickCapture from "../src/app/components/quick-capture";
import CollectionStart from "../src/app/components/collection-start";
import PersonalImage from "../src/app/components/personal-image";
import { blankDefinition, type Project } from "../src/lib/projects";
import {
  submissionAction,
  uploadImage,
  type Submission,
} from "../src/lib/submissions";
vi.mock("../src/lib/submissions", async () => ({
  ...(await vi.importActual<typeof import("../src/lib/submissions")>(
    "../src/lib/submissions",
  )),
  submissionAction: vi.fn(),
  uploadImage: vi.fn(),
}));
const project: Project = {
  id: "e084c03d-6fa3-445c-a479-26cbb697c7d4",
  owner_id: "b084c03d-6fa3-445c-a479-26cbb697c7d4",
  mode: "personal",
  visibility: "private",
  owner_images: 0,
  community_images: 0,
  remaining_slots: 500,
  status: "published",
  version: 1,
  published_version: 1,
  definition: {
    ...blankDefinition(),
    mode: "personal",
    name: "Manhole types",
    labels: [
      { key: "round", name: "Round", description: "" },
      { key: "square", name: "Square", description: "" },
    ],
    criteria: {
      schema_version: 1,
      questions: [
        {
          key: "notes",
          title: "Notes",
          type: "short_text",
          required: false,
          description: "",
          integer_only: false,
        },
      ],
    },
  },
  budget: 0,
  reserved_credits: 0,
  created_at: "2026-11-01T10:00:00Z",
  closing_date_passed: false,
};
const submission: Submission = {
  id: "c084c03d-6fa3-445c-a479-26cbb697c7d4",
  project_id: project.id,
  source: "owner",
  annotation_hash: "0".repeat(64),
  project_name: project.definition.name,
  criteria_version: 1,
  label_key: "round",
  label_name: "Round",
  answer_titles: {},
  answers: {},
  consent_record: {},
  status: "approved",
  qc_earned: 0,
  expired: false,
  hidden: false,
  image_deleted: false,
  width: 640,
  height: 640,
  image_format: "PNG",
  byte_size: 100,
  created_at: project.created_at,
  submitted_at: project.created_at,
  upload_expires_at: "2026-11-01T10:15:00Z",
};
const media = vi.fn();
beforeEach(() => {
  vi.stubGlobal(
    "URL",
    class extends URL {
      static createObjectURL = vi.fn(() => "blob:synthetic");
      static revokeObjectURL = vi.fn();
    },
  );
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: { getUserMedia: media },
  });
  vi.mocked(submissionAction).mockResolvedValue(submission);
  vi.mocked(uploadImage).mockResolvedValue(submission);
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.resetAllMocks();
});
function gallery(n = 1) {
  fireEvent.change(screen.getByLabelText("Choose from gallery"), {
    target: {
      files: Array.from(
        { length: n },
        (_, i) => new File(["image"], `image${i}.png`, { type: "image/png" }),
      ),
    },
  });
}
function attest() {
  fireEvent.click(
    screen.getByRole("checkbox", { name: /I own or have permission/ }),
  );
  fireEvent.click(
    screen.getByRole("checkbox", { name: /I will check each photo/ }),
  );
}
it("offers personal and crowdsourced modes separately from private visibility", () => {
  render(<CollectionStart />);
  fireEvent.click(
    screen.getByRole("button", { name: /Collect images myself/ }),
  );
  expect(screen.getByRole("heading", { name: /Private/ })).toBeVisible();
  expect(
    screen.getByRole("button", { name: "Create & open camera" }),
  ).toBeVisible();
  expect(screen.getByLabelText("Required label question")).toBeVisible();
});
it("creates private personal collections with one essential label and no funding step", async () => {
  const fetcher = vi.fn().mockResolvedValue(Response.json(project));
  vi.stubGlobal("fetch", fetcher);
  render(<CollectionStart />);
  fireEvent.click(
    screen.getByRole("button", { name: /Collect images myself/ }),
  );
  fireEvent.change(screen.getByLabelText("Collection name"), {
    target: { value: "Manholes" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Create & open camera" }));
  await vi.waitFor(() => expect(fetcher).toHaveBeenCalled());
  const body = JSON.parse(fetcher.mock.calls[0][1].body);
  expect(body.mode).toBe("personal");
  expect(body.labels).toHaveLength(4);
  expect(body.criteria.questions).toEqual([]);
});
it("uses touch choices and collapses optional metadata without requesting camera for gallery", () => {
  render(<QuickCapture project={project} owner />);
  gallery();
  expect(media).not.toHaveBeenCalled();
  expect(
    screen.getByText("More details (optional)").closest("details"),
  ).not.toHaveAttribute("open");
  fireEvent.click(screen.getByRole("button", { name: "Round" }));
  expect(screen.getByRole("button", { name: "Round" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  expect(
    screen.getByRole("button", { name: "Save & Capture Next" }),
  ).toBeDisabled();
});
it("requires a label and rights/privacy attestation before upload", async () => {
  render(<QuickCapture project={project} owner />);
  gallery();
  attest();
  fireEvent.click(screen.getByRole("button", { name: "Save & Capture Next" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Choose an image label",
  );
  expect(submissionAction).not.toHaveBeenCalled();
});
it("saves each selected image independently and retains consent within the collection session", async () => {
  render(<QuickCapture project={project} owner />);
  gallery(2);
  attest();
  fireEvent.click(screen.getByRole("button", { name: "Round" }));
  fireEvent.click(screen.getByRole("button", { name: "Save & Capture Next" }));
  await screen.findByText("Saved · 0 QC. Ready for next photo.");
  expect(screen.getByRole("button", { name: "Round" })).toHaveAttribute(
    "aria-pressed",
    "false",
  );
  fireEvent.click(screen.getByRole("button", { name: "Square" }));
  fireEvent.click(screen.getByRole("button", { name: "Save & Capture Next" }));
  await vi.waitFor(() => expect(uploadImage).toHaveBeenCalledTimes(2));
  expect(
    vi
      .mocked(submissionAction)
      .mock.calls.map((c) => (c[1] as { label_key: string }).label_key),
  ).toEqual(["round", "square"]);
  expect(
    screen.getByRole("checkbox", { name: /I own or have permission/ }),
  ).toBeChecked();
});
it("retries an interrupted upload using its original slot and frozen labels", async () => {
  vi.mocked(uploadImage)
    .mockRejectedValueOnce(new Error("Interrupted"))
    .mockResolvedValueOnce(submission);
  render(<QuickCapture project={project} owner />);
  gallery();
  attest();
  fireEvent.click(screen.getByRole("button", { name: "Round" }));
  fireEvent.click(screen.getByRole("button", { name: "Save & Capture Next" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("Interrupted");
  expect(screen.getByRole("button", { name: "Square" })).toBeDisabled();
  fireEvent.click(
    screen.getByRole("button", { name: "Retry save & capture next" }),
  );
  await screen.findByText("Saved · 0 QC. Ready for next photo.");
  expect(submissionAction).toHaveBeenCalledTimes(1);
  expect(uploadImage).toHaveBeenCalledTimes(2);
});
it("community capture saves for review rather than claiming immediate payment", async () => {
  render(
    <QuickCapture
      project={{ ...project, mode: "crowdsourced" }}
      owner={false}
    />,
  );
  gallery();
  attest();
  fireEvent.click(screen.getByRole("button", { name: "Square" }));
  fireEvent.click(screen.getByRole("button", { name: "Save & Capture Next" }));
  expect(
    await screen.findByText(
      "Submitted · Pending Review. Ready for next photo.",
    ),
  ).toBeVisible();
});
it("stops live camera tracks when leaving the capture flow", async () => {
  const stop = vi.fn();
  media.mockResolvedValue({ getTracks: () => [{ stop }] });
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
  const view = render(<QuickCapture project={project} owner />);
  fireEvent.click(screen.getByRole("button", { name: "Open live camera" }));
  await screen.findByRole("button", { name: "Take photo" });
  view.unmount();
  expect(stop).toHaveBeenCalled();
  vi.restoreAllMocks();
});
it("reports denied camera access while keeping gallery available", async () => {
  media.mockRejectedValue(new Error("Denied"));
  render(<QuickCapture project={project} owner />);
  fireEvent.click(screen.getByRole("button", { name: "Open live camera" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Camera access unavailable",
  );
  expect(screen.getByLabelText("Choose from gallery")).toBeInTheDocument();
});
it("rejects oversized or unsupported files before creating a slot", () => {
  render(<QuickCapture project={project} owner />);
  fireEvent.change(screen.getByLabelText("Choose from gallery"), {
    target: { files: [new File(["bad"], "bad.heic", { type: "image/heic" })] },
  });
  expect(screen.getByRole("alert")).toHaveTextContent("supported JPEG");
  expect(submissionAction).not.toHaveBeenCalled();
});
it("personal label edits send the optimistic annotation hash", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(Response.json(submission)));
  render(
    <PersonalImage
      submission={submission}
      definition={project.definition}
      editable
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Edit labels" }));
  fireEvent.click(screen.getByRole("button", { name: "Square" }));
  fireEvent.click(screen.getByRole("button", { name: "Save labels" }));
  await vi.waitFor(() => expect(fetch).toHaveBeenCalled());
  const calls = vi.mocked(fetch).mock.calls;
  const edit = calls.find((c) => String(c[0]).endsWith("/labels"));
  expect(edit).toBeTruthy();
  expect(JSON.parse(edit![1]!.body as string).expected_hash).toBe(
    submission.annotation_hash,
  );
});

it("returns to the same live camera after saving without another permission request", async () => {
  const stop = vi.fn();
  media.mockResolvedValue({ getTracks: () => [{ stop }] });
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
    drawImage: vi.fn(),
  } as unknown as CanvasRenderingContext2D);
  vi.spyOn(HTMLCanvasElement.prototype, "toBlob").mockImplementation(
    (callback) => callback(new Blob(["photo"], { type: "image/jpeg" })),
  );
  const view = render(<QuickCapture project={project} owner />);
  fireEvent.click(screen.getByRole("button", { name: "Open live camera" }));
  const take = await screen.findByRole("button", { name: "Take photo" });
  const video = screen.getByLabelText("Live camera preview");
  Object.defineProperties(video, {
    videoWidth: { configurable: true, value: 640 },
    videoHeight: { configurable: true, value: 640 },
  });
  fireEvent.click(take);
  attest();
  fireEvent.click(screen.getByRole("button", { name: "Round" }));
  fireEvent.click(screen.getByRole("button", { name: "Save & Capture Next" }));
  await screen.findByText("Saved · 0 QC. Ready for next photo.");
  expect(screen.getByRole("button", { name: "Take photo" })).toBeVisible();
  expect(video).toBeVisible();
  expect(media).toHaveBeenCalledTimes(1);
  expect(stop).not.toHaveBeenCalled();
  view.unmount();
  expect(stop).toHaveBeenCalled();
  vi.restoreAllMocks();
});
