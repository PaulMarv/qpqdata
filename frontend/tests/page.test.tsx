import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
vi.mock("../src/lib/api", () => ({
  getReadiness: vi.fn().mockResolvedValue(false),
}));
import Home from "../src/app/page";
it("renders current collection options and accessible service status", async () => {
  render(await Home());
  expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
    "Better datasets",
  );
  expect(
    screen.getByText(/Personal collections start private and cost 0 QC/),
  ).toBeVisible();
  expect(
    screen.getByRole("heading", { name: "Your images, your collection" }),
  ).toBeVisible();
  expect(screen.getByText(/Downloads always cost 0 QC/)).toBeVisible();
  expect(screen.getByRole("main")).toHaveAttribute("id", "main");
  expect(screen.getByRole("status")).toHaveTextContent("API: unavailable");
  expect(
    screen.getByRole("link", { name: /Browse free datasets/ }),
  ).toBeVisible();
});
