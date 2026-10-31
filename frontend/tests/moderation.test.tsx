import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import ReviewCard from "../src/app/components/review-card";
import SubmissionCard from "../src/app/components/submission-card";
import type { components } from "../src/lib/api-schema";
import { POST, GET } from "../src/app/api/moderation/[[...path]]/route";
const refresh = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }) }));
const item: components["schemas"]["ReviewItem"] = {
  contributor_name: "Test Contributor",
  reviewer_id: null,
  reviewed_at: null,
  submission: {
    id: "e084c03d-6fa3-445c-a479-26cbb697c7d4",
    project_id: "b084c03d-6fa3-445c-a479-26cbb697c7d4",
    project_name: "Kitchen scenes",
    criteria_version: 1,
    label_key: "clean",
    label_name: "Clean",
    answer_titles: { light: "Lighting" },
    answers: { light: "Daylight" },
    consent_record: {},
    status: "pending",
    expired: false,
    hidden: false,
    image_deleted: false,
    width: 16,
    height: 16,
    image_format: "PNG",
    byte_size: 80,
    created_at: "2026-10-31T12:00:00Z",
    submitted_at: "2026-10-31T12:00:00Z",
    upload_expires_at: "2026-10-31T12:15:00Z",
    qc_earned: 0,
    rejection_reason: null,
  },
};
beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
  refresh.mockClear();
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
it("requires rejection reason and displays version and labels", () => {
  render(<ReviewCard item={item} />);
  expect(screen.getByText(/Definition v1/)).toBeTruthy();
  expect(screen.getByText("Daylight")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Reject image" }));
  expect(screen.getByRole("status").textContent).toContain("rejection reason");
  expect(fetch).not.toHaveBeenCalled();
});
it("approves and refreshes the earned reward", async () => {
  vi.mocked(fetch).mockResolvedValue(Response.json({ qc_earned: 2 }));
  render(<ReviewCard item={item} />);
  fireEvent.click(screen.getByRole("button", { name: "Approve & award QC" }));
  await waitFor(() =>
    expect(screen.getByRole("status").textContent).toContain("2 QC awarded"),
  );
  expect(refresh).toHaveBeenCalledOnce();
  expect(JSON.parse(vi.mocked(fetch).mock.calls[0][1]?.body as string)).toEqual(
    { outcome: "approved", reason: "" },
  );
});
it("leaves failures retryable", async () => {
  vi.mocked(fetch).mockResolvedValue(
    Response.json(
      { detail: "Insufficient reserved approval capacity." },
      { status: 409 },
    ),
  );
  render(<ReviewCard item={item} />);
  fireEvent.click(screen.getByRole("button", { name: "Approve & award QC" }));
  await waitFor(() =>
    expect(screen.getByRole("status").textContent).toContain(
      "Insufficient reserved",
    ),
  );
  expect(refresh).not.toHaveBeenCalled();
  expect(
    screen.getByRole("button", { name: "Approve & award QC" }),
  ).not.toBeDisabled();
});
it("blocks hidden image approval and image loading", () => {
  render(
    <ReviewCard
      item={{ ...item, submission: { ...item.submission, hidden: true } }}
    />,
  );
  expect(
    screen.getByRole("button", { name: "Approve & award QC" }),
  ).toBeDisabled();
  expect(screen.queryByRole("img")).toBeNull();
});
it("shows contributor reasons and earned QC", () => {
  const { rerender } = render(
    <SubmissionCard
      submission={{
        ...item.submission,
        status: "rejected",
        rejection_reason: "Wrong scene",
      }}
    />,
  );
  expect(screen.getByText("Rejection reason: Wrong scene")).toBeTruthy();
  rerender(
    <SubmissionCard
      submission={{ ...item.submission, status: "approved", qc_earned: 2 }}
    />,
  );
  expect(screen.getByText("2 QC earned")).toBeTruthy();
  expect(screen.getByRole("button", { name: /request removal/ })).toBeTruthy();
});
it("proxy rejects cross-origin mutations and arbitrary paths", async () => {
  expect(
    (
      await POST(
        new Request("http://localhost:3000/api/moderation/x", {
          method: "POST",
          headers: { Origin: "https://evil.test" },
        }),
        { params: Promise.resolve({ path: [item.submission.id, "decision"] }) },
      )
    ).status,
  ).toBe(403);
  expect(
    (
      await GET(new Request("http://localhost:3000/api/moderation/x"), {
        params: Promise.resolve({ path: ["../private"] }),
      })
    ).status,
  ).toBe(404);
  expect(fetch).not.toHaveBeenCalled();
});
it("proxy forwards only session cookies and CSRF with no caching", async () => {
  vi.mocked(fetch).mockResolvedValue(
    Response.json({ status: "approved", qc_earned: 2 }),
  );
  const r = await POST(
    new Request(
      `http://localhost:3000/api/moderation/${item.submission.id}/decision`,
      {
        method: "POST",
        headers: {
          Origin: "http://localhost:3000",
          "Content-Type": "application/json",
          Cookie: "qpq_session=opaque; qpq_csrf=proof; unrelated=secret",
        },
        body: JSON.stringify({ outcome: "approved" }),
      },
    ),
    { params: Promise.resolve({ path: [item.submission.id, "decision"] }) },
  );
  expect(r.status).toBe(200);
  expect(r.headers.get("cache-control")).toBe("no-store");
  const forwarded = vi.mocked(fetch).mock.calls[0][0] as Request;
  expect(forwarded.headers.get("cookie")).not.toContain("unrelated");
  expect(forwarded.headers.get("x-csrf-token")).toBe("proof");
});
