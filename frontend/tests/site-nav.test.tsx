import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { usePathname } from "next/navigation";
import SiteNav from "../src/app/components/site-nav";

vi.mock("next/navigation", () => ({ usePathname: vi.fn() }));
afterEach(cleanup);

it.each([
  ["/projects", "Explore"],
  ["/projects/example/contribute", "Explore"],
  ["/datasets", "Datasets"],
  ["/datasets/example", "Datasets"],
])("marks the current section for %s", (pathname, label) => {
  vi.mocked(usePathname).mockReturnValue(pathname);
  render(<SiteNav />);
  const links = screen.getAllByRole("link");
  expect(screen.getByRole("link", { name: label })).toHaveAttribute(
    "aria-current",
    "page",
  );
  expect(
    links.filter((link) => link.hasAttribute("aria-current")),
  ).toHaveLength(1);
});

it.each(["/", "/profile", "/projects-other"])(
  "does not mark an unrelated route %s",
  (pathname) => {
    vi.mocked(usePathname).mockReturnValue(pathname);
    render(<SiteNav />);
    expect(
      screen.getByRole("navigation", { name: "Main navigation" }),
    ).toBeVisible();
    for (const link of screen.getAllByRole("link"))
      expect(link).not.toHaveAttribute("aria-current");
  },
);
