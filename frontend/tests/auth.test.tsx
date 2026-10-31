import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { useRouter } from "next/navigation";
import AccountNav from "../src/app/components/account-nav";
import LoginForm from "../src/app/components/login-form";
import VerifyForm from "../src/app/dev-email/verify/verify-form";
import { POST } from "../src/app/api/auth/[action]/route";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
  window.history.replaceState(null, "", "/");
});
it("shows only Log in and Sign up to guests", () => {
  render(<AccountNav user={null} />);
  const links = within(
    screen.getByRole("navigation", { name: "Account" }),
  ).getAllByRole("link");
  expect(links.map((link) => link.textContent)).toEqual(["Log in", "Sign up"]);
  expect(screen.queryByLabelText("Open profile menu")).toBeNull();
});
it("shows only an avatar with all required profile actions to signed-in users", () => {
  render(
    <AccountNav
      user={{ email: "student@university.test", display_name: "Student" }}
    />,
  );
  expect(screen.getByLabelText("Open profile menu")).toHaveTextContent("ST");
  expect(screen.queryByText("Log in")).toBeNull();
  expect(screen.queryByText("Sign up")).toBeNull();
  screen
    .getByLabelText("Open profile menu")
    .closest("details")
    ?.setAttribute("open", "");
  for (const name of [
    "My Profile",
    "My Collections",
    "My Submissions",
    "QPQ Wallet",
  ])
    expect(screen.getByRole("link", { name })).toBeVisible();
  expect(screen.getByRole("button", { name: "Sign Out" })).toBeVisible();
});
it("requests passwordless login without passwords", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValue(Response.json({ message: "Link requested" }));
  vi.stubGlobal("fetch", fetcher);
  render(<LoginForm />);
  fireEvent.change(screen.getByLabelText("School or work email"), {
    target: { value: "student@university.test" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Send login link" }));
  expect(await screen.findByRole("status")).toBeVisible();
  expect(JSON.parse(fetcher.mock.calls[0][1].body).intent).toBe("login");
  expect(document.querySelector('input[type="password"]')).toBeNull();
});
it("uses the separate authentication endpoint and refreshes navigation after login", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValue(Response.json({ status: "authenticated" }));
  vi.stubGlobal("fetch", fetcher);
  window.history.replaceState(
    null,
    "",
    "/verify-email#token=" + "x".repeat(43),
  );
  render(<VerifyForm authentication />);
  fireEvent.click(screen.getByRole("button", { name: "Verify email" }));
  await vi.waitFor(() =>
    expect(useRouter().replace).toHaveBeenCalledWith("/profile"),
  );
  expect(fetcher.mock.calls[0][0]).toBe("/api/auth/verify");
  expect(window.location.hash).toBe("");
});
it("blocks cross-origin authentication mutations", async () => {
  const response = await POST(
    new Request("http://localhost:3000/api/auth/logout", {
      method: "POST",
      headers: {
        Origin: "https://attacker.example",
        "Content-Type": "application/json",
      },
      body: "{}",
    }),
    { params: Promise.resolve({ action: "logout" }) },
  );
  expect(response.status).toBe(403);
});

it("dismisses the profile dropdown on outside pointer interaction", () => {
  render(
    <>
      <AccountNav
        user={{ email: "student@university.test", display_name: "Student" }}
      />
      <button>Outside</button>
    </>,
  );
  const details = screen
    .getByLabelText("Open profile menu")
    .closest("details")!;
  details.open = true;
  fireEvent.pointerDown(screen.getByRole("link", { name: "My Profile" }));
  expect(details.open).toBe(true);
  fireEvent.pointerDown(screen.getByRole("button", { name: "Outside" }));
  expect(details.open).toBe(false);
});
it("dismisses with Escape and returns keyboard focus to the avatar", () => {
  render(
    <AccountNav
      user={{ email: "student@university.test", display_name: "Student" }}
    />,
  );
  const avatar = screen.getByLabelText("Open profile menu");
  const details = avatar.closest("details")!;
  details.open = true;
  screen.getByRole("link", { name: "My Collections" }).focus();
  fireEvent.keyDown(document, { key: "Escape" });
  expect(details.open).toBe(false);
  expect(avatar).toHaveFocus();
});
it("closes the dropdown on link selection or focus leaving it", () => {
  render(
    <>
      <AccountNav
        user={{ email: "student@university.test", display_name: "Student" }}
      />
      <button>Outside</button>
    </>,
  );
  const details = screen
    .getByLabelText("Open profile menu")
    .closest("details")!;
  details.open = true;
  const profileLink = screen.getByRole("link", { name: "My Profile" });
  profileLink.addEventListener("click", (event) => event.preventDefault(), {
    once: true,
  });
  fireEvent.click(profileLink);
  expect(details.open).toBe(false);
  details.open = true;
  screen.getByRole("button", { name: "Outside" }).focus();
  expect(details.open).toBe(false);
});

it("replaces an expired avatar with guest links on a session check", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(new Response(null, { status: 401 })),
  );
  render(
    <AccountNav
      user={{ email: "student@university.test", display_name: "Student" }}
    />,
  );
  expect(await screen.findByRole("link", { name: "Log in" })).toBeVisible();
  expect(screen.queryByLabelText("Open profile menu")).toBeNull();
});
it("checks session validity when returning to the tab", async () => {
  const fetcher = vi.fn().mockResolvedValue(
    Response.json({
      email: "student@university.test",
      display_name: "Refreshed",
    }),
  );
  vi.stubGlobal("fetch", fetcher);
  render(
    <AccountNav
      user={{ email: "student@university.test", display_name: "Student" }}
    />,
  );
  await vi.waitFor(() => expect(fetcher).toHaveBeenCalledTimes(1));
  await vi.waitFor(() =>
    expect(screen.getByLabelText("Open profile menu")).toHaveTextContent("RE"),
  );
  fetcher.mockResolvedValue(new Response(null, { status: 401 }));
  fireEvent.focus(window);
  expect(await screen.findByRole("link", { name: "Sign up" })).toBeVisible();
});
it("keeps the avatar during a temporary session-service failure", async () => {
  const fetcher = vi.fn().mockRejectedValue(new Error("Offline"));
  vi.stubGlobal("fetch", fetcher);
  render(
    <AccountNav
      user={{ email: "student@university.test", display_name: "Student" }}
    />,
  );
  await vi.waitFor(() => expect(fetcher).toHaveBeenCalled());
  expect(screen.getByLabelText("Open profile menu")).toBeVisible();
});
it("clears the avatar immediately after logout without waiting for server navigation", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string) =>
      Promise.resolve(
        url.endsWith("/logout")
          ? Response.json({ status: "ok" })
          : Response.json({
              email: "student@university.test",
              display_name: "Student",
            }),
      ),
    ),
  );
  render(
    <AccountNav
      user={{ email: "student@university.test", display_name: "Student" }}
    />,
  );
  screen.getByLabelText("Open profile menu").closest("details")!.open = true;
  fireEvent.click(screen.getByRole("button", { name: "Sign Out" }));
  expect(await screen.findByRole("link", { name: "Log in" })).toBeVisible();
  expect(screen.queryByLabelText("Open profile menu")).toBeNull();
});
