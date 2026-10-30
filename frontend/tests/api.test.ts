import { afterEach, expect, it, vi } from "vitest";
import { getReadiness } from "../src/lib/api";
afterEach(() => vi.unstubAllGlobals());
it("recognises the typed healthy response", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok", service: "qpqdata-api" }), {
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );
  expect(await getReadiness("http://api.test")).toBe(true);
});
it("reports API failures without breaking the page", async () => {
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
  expect(await getReadiness("http://api.test")).toBe(false);
});
it("does not call a failing dependency ready", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "unavailable" }), {
        status: 503,
      }),
    ),
  );
  expect(await getReadiness("http://api.test")).toBe(false);
});
