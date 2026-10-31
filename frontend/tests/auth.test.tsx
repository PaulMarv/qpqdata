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
