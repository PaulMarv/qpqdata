import "@testing-library/jest-dom/vitest";

import { vi } from "vitest";
vi.mock("next/navigation", () => {
  const router = { push: vi.fn(), replace: vi.fn(), refresh: vi.fn() };
  return {
    useRouter: () => router,
    usePathname: () => "/profile",
    redirect: (url: string) => {
      throw new Error("REDIRECT:" + url);
    },
    notFound: () => {
      throw new Error("NOT_FOUND");
    },
  };
});
