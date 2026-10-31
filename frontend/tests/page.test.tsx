import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
vi.mock("../src/lib/api", () => ({
  getReadiness: vi.fn().mockResolvedValue(false),
}));
import Home from "../src/app/page";
it("renders the phase boundary and accessible service status", async () => {
  render(await Home());
  expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
    "Better datasets",
  );
  expect(screen.getByRole("main")).toHaveAttribute("id", "main");
  expect(screen.getByRole("status")).toHaveTextContent("API: unavailable");
  expect(
    screen.getByText(/and dataset downloads are not available/),
  ).toBeVisible();
});
