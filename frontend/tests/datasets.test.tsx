import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import DatasetDownload from "../src/app/components/dataset-download";
import ExportConsentForm from "../src/app/components/export-consent";
import DatasetReport from "../src/app/components/dataset-report";
import { GET, POST } from "../src/app/api/datasets/[[...path]]/route";
import type { Dataset } from "../src/lib/datasets";
const refresh = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ refresh }) }));
const dataset: Dataset = {
  id: "e084c03d-6fa3-445c-a479-26cbb697c7d4",
  collection_id: "b084c03d-6fa3-445c-a479-26cbb697c7d4",
  name: "Scenes",
  description: "Synthetic",
  purpose: "Testing",
  category: "science",
  image_count: 1,
  criteria_version: 1,
  criteria: { schema_version: 1, questions: [] },
  labels: [],
  licence: "CC0-1.0",
  licence_url: "https://creativecommons.org/publicdomain/zero/1.0/",
  reuse_terms: "Open reuse",
  updated_at: "2026-10-31T12:00:00Z",
  download_cost: 0,
  versions: [
    {
      downloadable: true,
      version: 1,
      image_count: 1,
      created_at: "2026-10-31T12:00:00Z",
      revoked: false,
      state: "ready",
      expires_at: "2099-01-01T00:00:00Z",
      byte_size: 100,
      sha256: "abc",
    },
  ],
};
beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
  refresh.mockClear();
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
it("displays zero QC and requires licence acknowledgement before downloading", () => {
  render(<DatasetDownload dataset={dataset} />);
  expect(screen.getByText("Download · Free · 0 QC")).toBeTruthy();
  const link = screen.getByText("Download version 1 · 0 QC");
  expect(link).not.toHaveAttribute("href");
  fireEvent.click(screen.getByRole("checkbox"));
  expect(link).toHaveAttribute(
    "href",
    `/api/datasets/${dataset.id}/versions/1/download`,
  );
});
it("prepares an expired or missing ZIP without a credit request", async () => {
  vi.mocked(fetch).mockResolvedValue(Response.json({ state: "queued" }));
  render(
    <DatasetDownload
      dataset={{
        ...dataset,
        versions: [{ ...dataset.versions[0], state: "failed" }],
      }}
    />,
  );
  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.click(
    screen.getByRole("button", { name: /Prepare or regenerate/ }),
  );
  await waitFor(() =>
    expect(screen.getByRole("status").textContent).toContain("queued"),
  );
  expect(fetch).toHaveBeenCalledWith(
    `/api/datasets/${dataset.id}/versions/1/prepare`,
    expect.objectContaining({ method: "POST" }),
  );
  expect(refresh).toHaveBeenCalledOnce();
});
it("never presents revoked versions as downloadable", () => {
  render(
    <DatasetDownload
      dataset={{
        ...dataset,
        versions: [
          { ...dataset.versions[0], revoked: true, downloadable: false },
        ],
      }}
    />,
  );
  expect(screen.queryByRole("link", { name: /Download version/ })).toBeNull();
  expect(screen.getByText(/permission changed/)).toBeTruthy();
});
it("reports backend preparation errors and allows retry", async () => {
  vi.mocked(fetch).mockResolvedValue(
    Response.json({ detail: "Export limit reached" }, { status: 413 }),
  );
  render(<DatasetDownload dataset={dataset} />);
  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.click(
    screen.getByRole("button", { name: /Prepare or regenerate/ }),
  );
  await waitFor(() =>
    expect(screen.getByRole("status").textContent).toContain("Export limit"),
  );
  expect(refresh).not.toHaveBeenCalled();
});
it("offers a privacy reporting pathway", () => {
  render(<DatasetReport id={dataset.id} />);
  expect(screen.getByRole("button", { name: "Send report" })).toBeTruthy();
  expect(screen.getByRole("textbox", { name: "Details" })).toBeRequired();
});
it("proxy rejects cross-origin requests and arbitrary file paths", async () => {
  const url =
    "http://localhost:3000/api/datasets/start/" + dataset.collection_id;
  expect(
    (
      await POST(
        new Request(url, {
          method: "POST",
          headers: { Origin: "https://evil.test" },
        }),
        { params: Promise.resolve({ path: ["start", dataset.collection_id] }) },
      )
    ).status,
  ).toBe(403);
  expect(
    (
      await GET(new Request(url), {
        params: Promise.resolve({ path: ["../secret"] }),
      })
    ).status,
  ).toBe(404);
  expect(fetch).not.toHaveBeenCalled();
});
it("streams a ZIP through the private proxy with no public cache", async () => {
  vi.mocked(fetch).mockResolvedValue(
    new Response("zip", {
      headers: { "Content-Type": "application/zip", "Content-Length": "3" },
    }),
  );
  const r = await GET(
    new Request("http://localhost:3000/api/datasets/x", {
      headers: { Cookie: "qpq_session=opaque; unrelated=secret" },
    }),
    {
      params: Promise.resolve({
        path: [dataset.id, "versions", "1", "download"],
      }),
    },
  );
  expect(r.status).toBe(200);
  expect(r.headers.get("content-type")).toBe("application/zip");
  expect(r.headers.get("cache-control")).toBe("no-store");
  expect(r.headers.get("content-disposition")).toContain("attachment");
  expect(await r.text()).toBe("zip");
  expect(
    (vi.mocked(fetch).mock.calls[0][1]?.headers as Record<string, string>)
      .Cookie,
  ).not.toContain("unrelated");
});
it("bounds JSON requests before forwarding", async () => {
  const r = await POST(
    new Request("http://localhost:3000/api/datasets/x", {
      method: "POST",
      headers: {
        Origin: "http://localhost:3000",
        "Content-Type": "application/json",
      },
      body: '"' + "x".repeat(8192) + '"',
    }),
    { params: Promise.resolve({ path: ["start", dataset.collection_id] }) },
  );
  expect(r.status).toBe(413);
  expect(fetch).not.toHaveBeenCalled();
});

it("keeps emails out of public attribution before submitting consent", async () => {
  vi.mocked(fetch)
    .mockResolvedValueOnce(
      Response.json({
        id: null,
        publication_id: dataset.id,
        public_fields: [],
        withdrawn: false,
        authorised: false,
        public_attribution: "",
      }),
    )
    .mockResolvedValueOnce(Response.json(dataset));
  render(<ExportConsentForm id="source" />);
  const alias = await screen.findByRole("textbox", {
    name: /Public attribution/,
  });
  fireEvent.change(alias, { target: { value: "private@example.test" } });
  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.submit(
    screen
      .getByRole("button", { name: "Allow public dataset distribution" })
      .closest("form")!,
  );
  expect(screen.getByRole("status").textContent).toContain("not an email");
  expect(fetch).toHaveBeenCalledTimes(2);
});

it("records explicit contributor opt-in without making a credit request", async () => {
  vi.mocked(fetch)
    .mockResolvedValueOnce(
      Response.json({
        id: null,
        publication_id: dataset.id,
        public_fields: [],
        withdrawn: false,
        authorised: false,
        public_attribution: "",
      }),
    )
    .mockResolvedValueOnce(Response.json(dataset))
    .mockResolvedValueOnce(
      Response.json({
        id: dataset.id,
        publication_id: dataset.id,
        public_fields: [],
        withdrawn: false,
        authorised: false,
        public_attribution: "Public Creator",
      }),
    );
  render(<ExportConsentForm id="source" />);
  const alias = await screen.findByRole("textbox", {
    name: /Public attribution/,
  });
  fireEvent.change(alias, { target: { value: "Public Creator" } });
  fireEvent.click(screen.getByRole("checkbox"));
  fireEvent.submit(
    screen
      .getByRole("button", { name: "Allow public dataset distribution" })
      .closest("form")!,
  );
  await waitFor(() =>
    expect(screen.getByRole("status").textContent).toContain(
      "consent recorded",
    ),
  );
  expect(fetch).toHaveBeenLastCalledWith(
    "/api/datasets/consent/source",
    expect.objectContaining({ method: "POST" }),
  );
});
