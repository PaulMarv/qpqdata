import { apiClient } from "../../../../lib/api";
import type { components } from "../../../../lib/api-schema";
export const runtime = "nodejs";
async function transport(
  request: Request,
  context: { params: Promise<{ path: string[] }> },
) {
  const reply = (detail: string, status: number) =>
    Response.json(
      { detail },
      { status, headers: { "Cache-Control": "no-store", Vary: "Cookie" } },
    );
  const path = (await context.params).path;
  const start = path[0] === "start",
    id = start ? path[1] : path[0],
    action = start ? "start" : path[1];
  if (
    !id ||
    !/^[0-9a-f-]{36}$/.test(id) ||
    path.length > 2 ||
    !(
      ["start", "image", "cancel", "removal-request", undefined] as unknown[]
    ).includes(action)
  )
    return reply("Not found", 404);
  const mutation = request.method !== "GET";
  const origin = (
    process.env.QPQ_FRONTEND_URL ?? "http://localhost:3000"
  ).replace(/\/$/, "");
  if (mutation && request.headers.get("origin") !== origin)
    return reply("Request rejected.", 403);
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
    ...(mutation && csrf ? { "X-CSRF-Token": csrf } : {}),
  };
  const base = process.env.QPQ_API_INTERNAL_URL ?? "http://localhost:8000";
  try {
    if (
      action === "image" &&
      (request.method === "PUT" || request.method === "GET")
    ) {
      const length = request.headers.get("content-length");
      if (length && Number(length) > 10 * 1024 * 1024)
        return reply("Image exceeds 10 MiB.", 413);
      let count = 0;
      const stream =
        request.method === "PUT"
          ? request.body?.pipeThrough(
              new TransformStream<Uint8Array, Uint8Array>({
                transform(chunk, controller) {
                  count += chunk.byteLength;
                  if (count > 10 * 1024 * 1024) {
                    controller.error(new Error("Image too large"));
                    return;
                  }
                  controller.enqueue(chunk);
                },
              }),
            )
          : undefined;
      const init: RequestInit & { duplex?: "half" } = {
        method: request.method,
        headers: { ...headers, "Content-Type": "application/octet-stream" },
        body: stream,
        duplex: stream ? "half" : undefined,
        cache: "no-store",
        signal: AbortSignal.timeout(60000),
      };
      const result = await fetch(
        base + "/api/v1/submissions/" + id + "/image",
        init,
      );
      return new Response(result.body, {
        status: result.status,
        headers: {
          "Content-Type":
            result.headers.get("content-type") ?? "application/json",
          "Cache-Control": "no-store",
          Vary: "Cookie",
          "X-Content-Type-Options": "nosniff",
        },
      });
    }
    const client = apiClient(base),
      opts = {
        headers,
        cache: "no-store" as const,
        signal: AbortSignal.timeout(12000),
      };
    if (request.method === "GET" && !action) {
      const r = await client.GET("/api/v1/submissions/{ident}", {
        ...opts,
        params: { path: { ident: id } },
      });
      return Response.json(r.data ?? r.error, {
        status: r.response.status,
        headers: { "Cache-Control": "no-store", Vary: "Cookie" },
      });
    }
    if (
      request.method !== "POST" ||
      !request.headers.get("content-type")?.startsWith("application/json")
    )
      return reply("JSON required", 415);
    const reader = request.body?.getReader();
    if (!reader) return reply("Invalid request", 400);
    const chunks: Uint8Array[] = [];
    let size = 0;
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > 65536) {
        await reader.cancel();
        return reply("Request too large", 413);
      }
      chunks.push(value);
    }
    let body;
    try {
      body = JSON.parse(Buffer.concat(chunks).toString("utf8"));
    } catch {
      return reply("Invalid request", 400);
    }
    let result;
    if (start)
      result = await client.POST("/api/v1/projects/{project_id}/submissions", {
        ...opts,
        params: { path: { project_id: id } },
        body: body as components["schemas"]["SubmissionRequest"],
      });
    else if (action === "cancel")
      result = await client.POST("/api/v1/submissions/{ident}/cancel", {
        ...opts,
        params: { path: { ident: id } },
      });
    else if (action === "removal-request")
      result = await client.POST(
        "/api/v1/submissions/{ident}/removal-request",
        { ...opts, params: { path: { ident: id } }, body },
      );
    else return reply("Not found", 404);
    return Response.json(result.data ?? result.error, {
      status: result.response.status,
      headers: { "Cache-Control": "no-store", Vary: "Cookie" },
    });
  } catch {
    return reply("Submission service unavailable. Retry safely.", 503);
  }
}
export const POST = transport;
export const GET = transport;
export const PUT = transport;
