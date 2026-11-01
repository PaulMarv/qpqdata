import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { useRouter } from "next/navigation";
import ProjectEditor from "../src/app/components/project-editor";
import ProjectActions from "../src/app/components/project-actions";
import ProjectDefinition from "../src/app/components/project-definition";
import { ProjectCard, Pagination } from "../src/app/components/project-card";
import { POST, PUT } from "../src/app/api/projects/[[...path]]/route";
import { blankDefinition, type Project } from "../src/lib/projects";
const project: Project = {
  mode: "crowdsourced",
  visibility: "private",
  owner_images: 0,
  community_images: 0,
  remaining_slots: 20,
  id: "e084c03d-6fa3-445c-a479-26cbb697c7d4",
  owner_id: "b084c03d-6fa3-445c-a479-26cbb697c7d4",
  status: "draft",
  version: 1,
  published_version: null,
  definition: { ...blankDefinition(), name: "Kitchens" },
  budget: 20,
  reserved_credits: 0,
  created_at: "2026-10-31T12:00:00Z",
  closing_date_passed: false,
};
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  vi.clearAllMocks();
});
it("saves a draft through the API with automatic IDs and default 1 QC reward", async () => {
  const f = vi.fn().mockResolvedValue(Response.json(project));
  vi.stubGlobal("fetch", f);
  render(<ProjectEditor />);
  expect(screen.getByLabelText("Project ID (automatic)")).toHaveValue(
    "Generated when you save your draft",
  );
  fireEvent.change(screen.getByLabelText("Project name (required)"), {
    target: { value: "Kitchens" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
  await vi.waitFor(() =>
    expect(useRouter().push).toHaveBeenCalledWith("/projects/" + project.id),
  );
  const body = JSON.parse(f.mock.calls[0][1].body);
  expect(body.name).toBe("Kitchens");
  expect(body.reward_per_image).toBe(1);
  expect(body.image_count).toBe(20);
  expect(body.criteria.schema_version).toBe(1);
  expect(body.id).toBeUndefined();
});
it("edits with the expected version and displays backend funding errors", async () => {
  const f = vi
    .fn()
    .mockResolvedValue(
      Response.json(
        { detail: "This draft changed. Reload before saving." },
        { status: 409 },
      ),
    );
  vi.stubGlobal("fetch", f);
  render(<ProjectEditor initial={project} />);
  fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "This draft changed",
  );
  expect(JSON.parse(f.mock.calls[0][1].body).expected_version).toBe(1);
  expect(f.mock.calls[0][1].method).toBe("PUT");
});
it("builds choice questions with configurable options and previews unsaved labels", () => {
  render(<ProjectEditor />);
  fireEvent.click(screen.getByRole("button", { name: "+ Add label" }));
  fireEvent.change(screen.getByLabelText("Label 1 name"), {
    target: { value: "Clean / organised" },
  });
  fireEvent.click(screen.getByRole("button", { name: "+ Add question" }));
  fireEvent.change(screen.getByLabelText("Question title"), {
    target: { value: "How would you classify this kitchen?" },
  });
  fireEvent.change(screen.getByLabelText("Option 1"), {
    target: { value: "Clean" },
  });
  fireEvent.change(screen.getByLabelText("Option 2"), {
    target: { value: "Messy" },
  });
  fireEvent.click(screen.getByRole("button", { name: "+ Add option" }));
  expect(screen.getByLabelText("Option 3")).toBeVisible();
  fireEvent.click(screen.getByLabelText("Remove option 3"));
  fireEvent.click(screen.getAllByRole("button", { name: "Preview draft" })[0]);
  expect(screen.getByText("Clean / organised")).toBeVisible();
  expect(
    screen.getByRole("group", { name: /How would you classify/ }),
  ).toHaveTextContent("Optional");
  expect(screen.getByRole("radio", { name: "Clean" })).toBeEnabled();
  expect(screen.queryByRole("button", { name: "Save draft" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Back to editor" }));
  expect(screen.getByLabelText("Option 1")).toHaveValue("Clean");
});
it("supports all five field types and removes stale rules when changing type", () => {
  render(<ProjectEditor />);
  fireEvent.click(screen.getByRole("button", { name: "+ Add question" }));
  const type = screen.getByLabelText("Field type");
  fireEvent.change(type, { target: { value: "multiple_choice" } });
  expect(screen.getByLabelText("min selections")).toBeVisible();
  expect(screen.getByLabelText("max selections")).toBeVisible();
  fireEvent.change(type, { target: { value: "short_text" } });
  expect(screen.getByLabelText("min length")).toBeVisible();
  expect(screen.queryByLabelText("Option 1")).toBeNull();
  fireEvent.change(type, { target: { value: "number" } });
  expect(screen.getByLabelText("min value")).toBeVisible();
  expect(screen.getByLabelText("Whole numbers only")).toBeVisible();
  expect(screen.queryByLabelText("min length")).toBeNull();
  fireEvent.change(type, { target: { value: "yes_no" } });
  expect(screen.queryByLabelText("min value")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Remove question 1" }));
  expect(screen.queryByLabelText("Field type")).toBeNull();
});
it("reorders questions without changing their stable keys", async () => {
  const f = vi.fn().mockResolvedValue(Response.json(project));
  vi.stubGlobal("fetch", f);
  render(<ProjectEditor initial={project} />);
  fireEvent.click(screen.getByRole("button", { name: "+ Add question" }));
  fireEvent.change(screen.getByLabelText("Question title"), {
    target: { value: "First" },
  });
  fireEvent.click(screen.getByRole("button", { name: "+ Add question" }));
  fireEvent.change(screen.getAllByLabelText("Question title")[1], {
    target: { value: "Second" },
  });
  fireEvent.click(screen.getAllByRole("button", { name: "Move up" })[1]);
  fireEvent.click(screen.getByRole("button", { name: "Save draft" }));
  await vi.waitFor(() => expect(f).toHaveBeenCalled());
  const qs = JSON.parse(f.mock.calls[0][1].body).definition.criteria.questions;
  expect(qs.map((q: { title: string }) => q.title)).toEqual([
    "Second",
    "First",
  ]);
  expect(qs[0].key).not.toBe(qs[1].key);
});
it("requires explicit publication confirmation and sends the server version", async () => {
  vi.spyOn(window, "confirm").mockReturnValue(true);
  const f = vi
    .fn()
    .mockResolvedValue(Response.json({ ...project, status: "published" }));
  vi.stubGlobal("fetch", f);
  render(<ProjectActions project={project} />);
  fireEvent.click(
    screen.getByRole("button", { name: "Publish · reserve 20 QC" }),
  );
  await vi.waitFor(() => expect(useRouter().refresh).toHaveBeenCalled());
  expect(JSON.parse(f.mock.calls[0][1].body)).toEqual({
    status: "published",
    expected_version: 1,
  });
  expect(window.confirm).toHaveBeenCalledWith(expect.stringContaining("20 QC"));
});
it("does not send a close request when cancelled", () => {
  vi.spyOn(window, "confirm").mockReturnValue(false);
  const f = vi.fn();
  vi.stubGlobal("fetch", f);
  render(
    <ProjectActions
      project={{ ...project, status: "paused", reserved_credits: 20 }}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Close collection" }));
  expect(f).not.toHaveBeenCalled();
  expect(screen.getByText(/20 QC reserved/)).toBeVisible();
  expect(screen.queryByRole("link", { name: "Edit draft" })).toBeNull();
});
it("shows funding failures without reporting publication success", async () => {
  vi.spyOn(window, "confirm").mockReturnValue(true);
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(
        Response.json({ detail: "Insufficient QC." }, { status: 409 }),
      ),
  );
  render(<ProjectActions project={project} />);
  fireEvent.click(
    screen.getByRole("button", { name: "Publish · reserve 20 QC" }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Insufficient QC.",
  );
  expect(useRouter().refresh).not.toHaveBeenCalled();
});
it("shows label definitions, image rules and read-only contributor questions", () => {
  const d = {
    ...project.definition,
    labels: [
      { key: "clean", name: "Clean", description: "No visible clutter" },
    ],
    criteria: {
      schema_version: 1 as const,
      questions: [
        {
          key: "light",
          title: "Lighting",
          description: "Ambient light",
          type: "yes_no" as const,
          required: false,
          integer_only: false,
        },
      ],
    },
  };
  render(<ProjectDefinition definition={d} />);
  expect(screen.getByText("No visible clutter")).toBeVisible();
  expect(screen.getByText(/640 × 640/)).toBeVisible();
  expect(screen.getByLabelText("Lighting")).toBeDisabled();
});
it("renders project identifiers and real server pagination links", () => {
  render(
    <>
      <ProjectCard project={project} owner />
      <Pagination
        page={2}
        total={25}
        size={10}
        href={(n) => "/projects?page=" + n}
      />
    </>,
  );
  expect(screen.getByText("ID " + project.id)).toBeVisible();
  expect(screen.getByRole("link", { name: /Edit draft/ })).toHaveAttribute(
    "href",
    "/collections/" + project.id + "/edit",
  );
  const nav = screen.getByRole("navigation", { name: "Project pages" });
  expect(within(nav).getByText("Page 2 of 3 · 25 projects")).toBeVisible();
  expect(within(nav).getByRole("link", { name: /Next/ })).toHaveAttribute(
    "href",
    "/projects?page=3",
  );
});
it("blocks cross-origin and oversized project mutations", async () => {
  const context = { params: Promise.resolve({ path: [] }) };
  const rejected = await POST(
    new Request("http://localhost:3000/api/projects", {
      method: "POST",
      headers: {
        Origin: "https://attacker.example",
        "Content-Type": "application/json",
      },
      body: "{}",
    }),
    context,
  );
  expect(rejected.status).toBe(403);
  const oversized = await POST(
    new Request("http://localhost:3000/api/projects", {
      method: "POST",
      headers: {
        Origin: "http://localhost:3000",
        "Content-Type": "application/json",
      },
      body: "x".repeat(524289),
    }),
    context,
  );
  expect(oversized.status).toBe(413);
});
it("forwards only authenticated cookies and CSRF to the typed project API", async () => {
  const f = vi.fn().mockResolvedValue(Response.json(project));
  vi.stubGlobal("fetch", f);
  const response = await PUT(
    new Request("http://localhost:3000/api/projects/" + project.id, {
      method: "PUT",
      headers: {
        Origin: "http://localhost:3000",
        "Content-Type": "application/json",
        Cookie: "qpq_session=session; qpq_csrf=csrf; unrelated=private",
      },
      body: JSON.stringify({
        expected_version: 1,
        definition: project.definition,
      }),
    }),
    { params: Promise.resolve({ path: [project.id] }) },
  );
  expect(response.status).toBe(200);
  const forwarded = f.mock.calls[0][0] as Request;
  expect(forwarded.headers.get("cookie")).toBe(
    "qpq_session=session; qpq_csrf=csrf",
  );
  expect(forwarded.headers.get("x-csrf-token")).toBe("csrf");
  expect(forwarded.method).toBe("PUT");
});
