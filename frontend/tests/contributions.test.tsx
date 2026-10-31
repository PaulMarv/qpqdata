import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import Contributor from "../src/app/components/contributor";
import ImageLabels from "../src/app/components/image-labels";
import SubmissionCard from "../src/app/components/submission-card";
import { blankDefinition, type Project } from "../src/lib/projects";
import {
  submissionAction,
  uploadImage,
  validateLabels,
  type Submission,
} from "../src/lib/submissions";
import { POST, PUT, GET } from "../src/app/api/submissions/[...path]/route";
vi.mock("../src/lib/submissions", async () => {
  const actual = await vi.importActual<typeof import("../src/lib/submissions")>(
    "../src/lib/submissions",
  );
  return { ...actual, submissionAction: vi.fn(), uploadImage: vi.fn() };
});
const project: Project = {
  id: "e084c03d-6fa3-445c-a479-26cbb697c7d4",
  owner_id: "b084c03d-6fa3-445c-a479-26cbb697c7d4",
  status: "published",
  version: 1,
  published_version: 1,
  definition: {
    ...blankDefinition(),
    name: "Kitchens",
    labels: [
      { key: "clean", name: "Clean", description: "" },
      { key: "messy", name: "Messy", description: "" },
    ],
    criteria: {
      schema_version: 1,
      questions: [
        {
          key: "condition",
          title: "Condition",
          type: "single_choice",
          required: true,
          integer_only: false,
          description: "Choose the condition",
          options: ["Clean", "Messy"],
        },
      ],
    },
  },
  budget: 20,
  reserved_credits: 20,
  created_at: "2026-10-31T12:00:00Z",
  closing_date_passed: false,
};
const submission: Submission = {
  id: "c084c03d-6fa3-445c-a479-26cbb697c7d4",
  project_id: project.id,
  project_name: "Kitchens",
  criteria_version: 1,
  label_key: "clean",
  label_name: "Clean",
  answer_titles: { condition: "Condition" },
  answers: { condition: "Clean" },
  consent_record: {
    licence: "CC0-1.0",
    reuse_terms: "Research",
    statement: "I own this image",
  },
  status: "pending",
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
  upload_expires_at: "2026-10-31T12:15:00Z",
};
beforeEach(() => {
  vi.stubGlobal(
    "URL",
    class extends URL {
      static createObjectURL = vi.fn(() => "blob:synthetic");
      static revokeObjectURL = vi.fn();
    },
  );
  vi.mocked(submissionAction).mockResolvedValue(submission);
  vi.mocked(uploadImage).mockResolvedValue(submission);
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  vi.clearAllMocks();
});
function select(count = 1) {
  fireEvent.click(
    screen.getByRole("button", { name: "Continue to image selection" }),
  );
  const files = Array.from(
    { length: count },
    (_, i) =>
      new File(["synthetic"], "scene" + i + ".png", { type: "image/png" }),
  );
  fireEvent.change(screen.getByLabelText("Choose from gallery"), {
    target: { files },
  });
  return files;
}
function label(index = 0, value = "Clean") {
  const section = screen
    .getByRole("heading", { name: new RegExp("Image " + (index + 1) + " ·") })
    .closest("section")!;
  fireEvent.change(within(section).getByLabelText("Image label (required)"), {
    target: { value: value.toLowerCase() },
  });
  fireEvent.change(within(section).getByLabelText("Condition"), {
    target: { value },
  });
}
function confirm() {
  fireEvent.click(screen.getByRole("button", { name: /Review \d images/ }));
  fireEvent.click(screen.getByLabelText(/I own or have permission/));
  fireEvent.click(screen.getByLabelText(/I have checked/));
}
it("starts with image requirements and clear privacy/originality warnings", () => {
  render(<Contributor project={project} />);
  expect(
    screen.getByText(/File checks do not prove originality/),
  ).toBeVisible();
  expect(screen.queryByLabelText("Choose from gallery")).toBeNull();
});
it("separates camera capture from multiple gallery selection without invoking getUserMedia", () => {
  const media = vi.fn();
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: { getUserMedia: media },
  });
  render(<Contributor project={project} />);
  select(2);
  expect(screen.getByLabelText("Take a photo")).toHaveAttribute(
    "capture",
    "environment",
  );
  expect(screen.getByLabelText("Choose from gallery")).not.toHaveAttribute(
    "capture",
  );
  expect(screen.getByLabelText("Choose from gallery")).toHaveAttribute(
    "multiple",
  );
  expect(screen.getAllByRole("img")).toHaveLength(2);
  expect(media).not.toHaveBeenCalled();
});
it("keeps labels independent for each selected photo and requires every answer", () => {
  render(<Contributor project={project} />);
  select(2);
  label(0);
  fireEvent.click(screen.getByRole("button", { name: "Review 2 images" }));
  expect(screen.getByRole("alert")).toHaveTextContent("scene1.png");
  label(1, "Messy");
  fireEvent.click(screen.getByRole("button", { name: "Review 2 images" }));
  expect(
    screen.getByRole("heading", { name: "Review your images" }),
  ).toBeVisible();
  expect(screen.getByText("Condition: Clean")).toBeVisible();
  expect(screen.getByText("Condition: Messy")).toBeVisible();
  expect(
    screen.getByRole("button", { name: "Submit 2 images" }),
  ).toBeDisabled();
});
it("supports removal and replacement/retake with preview cleanup", () => {
  render(<Contributor project={project} />);
  select(2);
  fireEvent.change(screen.getByLabelText("Retake image 1"), {
    target: {
      files: [new File(["next"], "replacement.png", { type: "image/png" })],
    },
  });
  expect(
    screen.getByRole("heading", { name: "Image 1 · replacement.png" }),
  ).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Remove image 2" }));
  expect(screen.getAllByRole("img")).toHaveLength(1);
  expect(URL.revokeObjectURL).toHaveBeenCalledTimes(2);
});
it("rejects unsupported, oversized and over-limit selections before networking", () => {
  render(<Contributor project={project} />);
  select(0);
  const picker = screen.getByLabelText("Choose from gallery");
  fireEvent.change(picker, {
    target: { files: [new File(["x"], "phone.heic", { type: "image/heic" })] },
  });
  expect(screen.getByRole("alert")).toHaveTextContent("HEIC");
  const large = new File(["x"], "large.png", { type: "image/png" });
  Object.defineProperty(large, "size", { value: 10 * 1024 * 1024 + 1 });
  fireEvent.change(picker, { target: { files: [large] } });
  expect(screen.getByRole("alert")).toHaveTextContent("10 MiB");
  fireEvent.change(picker, {
    target: {
      files: Array.from(
        { length: 6 },
        () => new File(["x"], "a.png", { type: "image/png" }),
      ),
    },
  });
  expect(screen.getByRole("alert")).toHaveTextContent("five");
  expect(submissionAction).not.toHaveBeenCalled();
});
it("uploads after explicit consent, displays progress and confirms pending review", async () => {
  vi.mocked(uploadImage).mockImplementation(async (_id, _file, progress) => {
    progress(100);
    return submission;
  });
  render(<Contributor project={project} />);
  select();
  label();
  confirm();
  fireEvent.click(screen.getByRole("button", { name: "Submit 1 images" }));
  expect(await screen.findByText(/Submitted · Pending Review/)).toBeVisible();
  expect(submissionAction).toHaveBeenCalledWith(
    "start/" + project.id,
    expect.objectContaining({
      criteria_version: 1,
      label_key: "clean",
      answers: { condition: "Clean" },
      consent: true,
      privacy_acknowledgement: true,
    }),
  );
  expect(screen.getByRole("link", { name: "My Submissions" })).toHaveAttribute(
    "href",
    "/submissions",
  );
});
it("retries a failed upload with the same slot and no duplicate manifest", async () => {
  vi.mocked(uploadImage)
    .mockRejectedValueOnce(new Error("Connection interrupted"))
    .mockResolvedValueOnce(submission);
  render(<Contributor project={project} />);
  select();
  label();
  confirm();
  fireEvent.click(screen.getByRole("button", { name: "Submit 1 images" }));
  fireEvent.click(
    await screen.findByRole("button", { name: "Retry failed images" }),
  );
  expect(await screen.findByText(/Submitted · Pending Review/)).toBeVisible();
  expect(submissionAction).toHaveBeenCalledTimes(1);
  expect(vi.mocked(uploadImage).mock.calls.map((c) => c[0])).toEqual([
    submission.id,
    submission.id,
  ]);
});
it("supports all five answer types including a required false answer", () => {
  const d = {
    ...project.definition,
    criteria: {
      schema_version: 1 as const,
      questions: [
        {
          key: "flag",
          title: "Has daylight?",
          type: "yes_no" as const,
          required: true,
          integer_only: false,
          description: "",
        },
        {
          key: "n",
          title: "Count",
          type: "number" as const,
          required: false,
          integer_only: true,
          description: "",
          min_value: 0,
          max_value: 3,
        },
        {
          key: "text",
          title: "Notes",
          type: "short_text" as const,
          required: false,
          integer_only: false,
          description: "",
          max_length: 5,
        },
        {
          key: "multi",
          title: "Lighting",
          type: "multiple_choice" as const,
          required: false,
          integer_only: false,
          description: "",
          options: ["Day", "Indoor"],
        },
      ],
    },
  };
  const onAnswer = vi.fn();
  render(
    <ImageLabels
      definition={d}
      prefix="one"
      label="clean"
      answers={{ flag: false }}
      onLabel={vi.fn()}
      onAnswer={onAnswer}
    />,
  );
  expect(screen.getByLabelText("Has daylight?")).toHaveValue("false");
  expect(validateLabels(d, "clean", { flag: false, n: 0 })).toBeNull();
  expect(validateLabels(d, "clean", { flag: false, n: 1.5 })).toContain(
    "Count",
  );
  fireEvent.click(screen.getByLabelText("Day"));
  expect(onAnswer).toHaveBeenCalledWith("multi", ["Day"]);
  expect(screen.getByLabelText("Notes")).toHaveAttribute("maxlength", "5");
});
it("provides private thumbnails, retry recovery and removal suppression UI", async () => {
  const { rerender } = render(<SubmissionCard submission={submission} />);
  expect(screen.getByRole("img")).toHaveAttribute(
    "src",
    "/api/submissions/" + submission.id + "/image",
  );
  fireEvent.click(
    screen.getByRole("button", { name: "Report a concern / request removal" }),
  );
  fireEvent.click(
    screen.getByRole("button", { name: "Send removal request & hide image" }),
  );
  expect(await screen.findByRole("status")).toHaveTextContent(
    "Removal request recorded",
  );
  rerender(<SubmissionCard submission={{ ...submission, hidden: true }} />);
  expect(screen.queryByRole("img")).toBeNull();
  rerender(
    <SubmissionCard
      submission={{
        ...submission,
        status: "uploading",
        submitted_at: null,
        width: null,
        height: null,
      }}
    />,
  );
  expect(screen.getByLabelText("Retry image upload")).toBeVisible();
});
it("blocks cross-origin upload proxy requests and oversized declarations", async () => {
  const context = {
    params: Promise.resolve({ path: [submission.id, "image"] }),
  };
  const denied = await PUT(
    new Request(
      "http://localhost:3000/api/submissions/" + submission.id + "/image",
      {
        method: "PUT",
        headers: { Origin: "https://attacker.example" },
        body: "bad",
      },
    ),
    context,
  );
  expect(denied.status).toBe(403);
  const large = await PUT(
    new Request(
      "http://localhost:3000/api/submissions/" + submission.id + "/image",
      {
        method: "PUT",
        headers: {
          Origin: "http://localhost:3000",
          "Content-Length": String(10 * 1024 * 1024 + 1),
        },
        body: "bad",
      },
    ),
    context,
  );
  expect(large.status).toBe(413);
});
it("forwards only auth cookies to private image access with no public cache", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValue(
      new Response("sanitized", { headers: { "Content-Type": "image/png" } }),
    );
  vi.stubGlobal("fetch", fetcher);
  const result = await GET(
    new Request(
      "http://localhost:3000/api/submissions/" + submission.id + "/image",
      { headers: { Cookie: "qpq_session=test; unrelated=private" } },
    ),
    { params: Promise.resolve({ path: [submission.id, "image"] }) },
  );
  expect(result.headers.get("cache-control")).toBe("no-store");
  expect(fetcher.mock.calls[0][1].headers.Cookie).toBe("qpq_session=test");
  expect(await result.text()).toBe("sanitized");
});
it("rejects malformed submission JSON before calling the backend", async () => {
  const fetcher = vi.fn();
  vi.stubGlobal("fetch", fetcher);
  const r = await POST(
    new Request("http://localhost:3000/api/submissions/start/" + project.id, {
      method: "POST",
      headers: {
        Origin: "http://localhost:3000",
        "Content-Type": "application/json",
      },
      body: "{",
    }),
    { params: Promise.resolve({ path: ["start", project.id] }) },
  );
  expect(r.status).toBe(400);
  expect(fetcher).not.toHaveBeenCalled();
});

it("keeps the current preview when a replacement picker is cancelled", () => {
  render(<Contributor project={project} />);
  select();
  fireEvent.change(screen.getByLabelText("Replace image 1"), {
    target: { files: [] },
  });
  expect(
    screen.getByRole("heading", { name: "Image 1 · scene0.png" }),
  ).toBeVisible();
  expect(screen.getAllByRole("img")).toHaveLength(1);
});
it("shows transfer progress and a distinct validating state before confirmation", async () => {
  let finish: ((value: Submission) => void) | undefined;
  let update: ((value: number) => void) | undefined;
  vi.mocked(uploadImage).mockImplementation((_id, _file, progress) => {
    update = progress;
    return new Promise((resolve) => {
      finish = resolve;
    });
  });
  render(<Contributor project={project} />);
  select();
  label();
  confirm();
  fireEvent.click(screen.getByRole("button", { name: "Submit 1 images" }));
  await vi.waitFor(() => expect(update).toBeDefined());
  const { act } = await import("@testing-library/react");
  await act(async () => update?.(33));
  expect(screen.getByRole("progressbar")).toHaveAttribute("value", "33");
  await act(async () => update?.(100));
  expect(screen.getByText("Validating and saving…")).toBeVisible();
  await act(async () => finish?.(submission));
  expect(screen.getByText(/Submitted · Pending Review/)).toBeVisible();
});
