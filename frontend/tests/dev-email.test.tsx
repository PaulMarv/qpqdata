import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import EmailForm from "../src/app/dev-email/email-form";
import VerifyForm from "../src/app/dev-email/verify/verify-form";
import { POST } from "../src/app/api/dev-email/[action]/route";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
  window.history.replaceState(null, "", "/");
});
it("registers the example mailbox and displays Mailpit guidance", async () => {
  const fetcher = vi
    .fn()
    .mockResolvedValue(
      Response.json({ message: "Check Mailpit for your verification email." }),
    );
  vi.stubGlobal("fetch", fetcher);
  render(<EmailForm />);
  expect(screen.getByLabelText("Test email address")).toHaveValue(
    "student@university.test",
  );
  fireEvent.click(
    screen.getByRole("button", { name: "Register test account" }),
  );
  expect(
    await screen.findByText("Check Mailpit for your verification email."),
  ).toBeVisible();
  expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({
    email: "student@university.test",
  });
});
it("removes the token fragment and consumes it only on explicit confirmation", async () => {
  const token = "a".repeat(43);
  window.history.replaceState(null, "", "/dev-email/verify#token=" + token);
  const fetcher = vi
    .fn()
    .mockResolvedValue(
      Response.json({ message: "Development account activated." }),
    );
  vi.stubGlobal("fetch", fetcher);
  render(<VerifyForm />);
  expect(window.location.hash).toBe("");
  expect(fetcher).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole("button", { name: "Verify email" }));
  expect(
    await screen.findByText("Development account activated."),
  ).toBeVisible();
  expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({ token });
  expect(screen.getByRole("button", { name: "Verify email" })).toBeDisabled();
});
it("reports missing links without sending a request", async () => {
  const fetcher = vi.fn();
  vi.stubGlobal("fetch", fetcher);
  render(<VerifyForm />);
  fireEvent.click(screen.getByRole("button", { name: "Verify email" }));
  expect(screen.getByRole("status")).toHaveTextContent(
    "Link invalid or expired",
  );
  expect(fetcher).not.toHaveBeenCalled();
});
it("keeps the frontend transport disabled in production", async () => {
  vi.stubEnv("QPQ_ENVIRONMENT", "production");
  vi.stubEnv("QPQ_DEV_EMAIL_ENABLED", "true");
  const response = await POST(
    new Request("http://localhost:3000/api/dev-email/register", {
      method: "POST",
    }),
    { params: Promise.resolve({ action: "register" }) },
  );
  expect(response.status).toBe(404);
});
it("rejects cross-origin verification requests", async () => {
  vi.stubEnv("QPQ_ENVIRONMENT", "development");
  vi.stubEnv("QPQ_DEV_EMAIL_ENABLED", "true");
  const response = await POST(
    new Request("http://localhost:3000/api/dev-email/verify", {
      method: "POST",
      headers: { Origin: "https://unknown.example" },
    }),
    { params: Promise.resolve({ action: "verify" }) },
  );
  expect(response.status).toBe(403);
});
