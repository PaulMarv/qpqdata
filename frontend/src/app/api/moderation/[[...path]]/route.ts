import { apiClient } from "../../../../lib/api";
import type { components } from "../../../../lib/api-schema";
export const runtime = "nodejs";
async function transport(
  request: Request,
  context: { params: Promise<{ path?: string[] }> },
) {
  const reply = (value: unknown, status: number) =>
    Response.json(value, {
      status,
      headers: { "Cache-Control": "no-store", Vary: "Cookie" },
    });
  const path = (await context.params).path ?? [];
  const id = path[0];
  if (
    path.length > 2 ||
    (id && !/^[0-9a-f-]{36}$/.test(id)) ||
    (path[1] &&
      !["decision", "image", "moderators", "removal-request"].includes(path[1]))
  )
    return reply({ detail: "Not found" }, 404);
  const origin = (
    process.env.QPQ_FRONTEND_URL ?? "http://localhost:3000"
  ).replace(/\/$/, "");
  if (request.method !== "GET" && request.headers.get("origin") !== origin)
    return reply({ detail: "Request rejected." }, 403);
  const cookie = (request.headers.get("cookie") ?? "")
    .split(";")
    .map((s) => s.trim())
    .filter((s) => /^(?:__Host-)?qpq_(?:session|csrf)=/.test(s))
    .join("; ");
  const csrf = cookie
    .split(";")
    .map((s) => s.trim())
    .find((s) => /^(?:__Host-)?qpq_csrf=/.test(s))
    ?.split("=")[1];
  const headers = {
    Cookie: cookie,
    Origin: origin,
    ...(csrf ? { "X-CSRF-Token": csrf } : {}),
  };
  const base = process.env.QPQ_API_INTERNAL_URL ?? "http://localhost:8000";
  const opts = {
    headers,
    cache: "no-store" as const,
    signal: AbortSignal.timeout(12000),
  };
  const client = apiClient(base);
  try {
    if (request.method === "GET" && !id) {
      const q = new URL(request.url).searchParams;
      const status = q.get("status");
      if (status && !["pending", "approved", "rejected"].includes(status))
        return reply({ detail: "Invalid status" }, 400);
      const r = await client.GET("/api/v1/moderation", {
        ...opts,
        params: {
          query: {
            project_id: q.get("project_id") || undefined,
            status: status as "pending" | "approved" | "rejected" | undefined,
            page: Number(q.get("page") || 1),
            page_size: 10,
          },
        },
      });
      return reply(r.data ?? r.error, r.response.status);
    }
    if (request.method === "GET" && id && path[1] === "image") {
      const r = await fetch(`${base}/api/v1/moderation/${id}/image`, opts);
      return new Response(r.body, {
        status: r.status,
        headers: {
          "Content-Type": r.headers.get("content-type") ?? "application/json",
          "Cache-Control": "no-store",
          Vary: "Cookie",
          "X-Content-Type-Options": "nosniff",
        },
      });
    }
    if (
      request.method !== "POST" ||
      !id ||
      !["decision", "moderators", "removal-request"].includes(path[1])
    )
      return reply({ detail: "Not found" }, 404);
    if (!request.headers.get("content-type")?.startsWith("application/json"))
      return reply({ detail: "JSON required" }, 415);
    const reader = request.body?.getReader();
    if (!reader) return reply({ detail: "Invalid request" }, 400);
    let count = 0;
    const chunks: Uint8Array[] = [];
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      count += value.byteLength;
      if (count > 8192) {
        await reader.cancel();
        return reply({ detail: "Request too large" }, 413);
      }
      chunks.push(value);
    }
    let body;
    try {
      body = JSON.parse(Buffer.concat(chunks).toString("utf8"));
    } catch {
      return reply({ detail: "Invalid request" }, 400);
    }
    if (path[1] === "moderators") {
      const r = await client.POST("/api/v1/projects/{project_id}/moderators", {
        ...opts,
        params: { path: { project_id: id } },
        body: body as components["schemas"]["ModeratorRequest"],
      });
      return r.response.status === 204
        ? new Response(null, {
            status: 204,
            headers: { "Cache-Control": "no-store" },
          })
        : reply(r.error, r.response.status);
    }
    if (path[1] === "removal-request") {
      const r = await client.POST(
        "/api/v1/moderation/{ident}/removal-request",
        {
          ...opts,
          params: { path: { ident: id } },
          body: body as components["schemas"]["RemovalBody"],
        },
      );
      return reply(r.data ?? r.error, r.response.status);
    }
    const r = await client.POST("/api/v1/moderation/{ident}/decision", {
      ...opts,
      params: { path: { ident: id } },
      body: body as components["schemas"]["DecisionRequest"],
    });
    return reply(r.data ?? r.error, r.response.status);
  } catch {
    return reply({ detail: "Review service unavailable. Retry safely." }, 503);
  }
}
export const GET = transport;
export const POST = transport;
