import { apiClient } from "../../../../lib/api";
import type { Definition } from "../../../../lib/projects";
async function transport(
  request: Request,
  context: { params: Promise<{ path?: string[] }> },
) {
  const reply = (detail: string, status: number) =>
    Response.json(
      { detail },
      { status, headers: { "Cache-Control": "no-store" } },
    );
  const parts = (await context.params).path ?? [];
  const id = parts[0];
  if (
    parts.length > 2 ||
    (id && !/^[0-9a-f-]{36}$/.test(id)) ||
    (parts.length === 2 && parts[1] !== "status")
  )
    return reply("Not found", 404);
  const origin = (
    process.env.QPQ_FRONTEND_URL ?? "http://localhost:3000"
  ).replace(/\/$/, "");
  if (request.headers.get("origin") !== origin)
    return reply("Request rejected.", 403);
  if (!request.headers.get("content-type")?.startsWith("application/json"))
    return reply("JSON required", 415);
  try {
    const reader = request.body?.getReader();
    if (!reader) return reply("Invalid request", 400);
    const chunks: Uint8Array[] = [];
    let size = 0;
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > 524288) {
        await reader.cancel();
        return reply("Request too large", 413);
      }
      chunks.push(value);
    }
    const body = JSON.parse(Buffer.concat(chunks).toString("utf8"));
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
    const opts = {
      headers: {
        Cookie: cookie,
        Origin: origin,
        ...(csrf ? { "X-CSRF-Token": csrf } : {}),
      },
      cache: "no-store" as const,
      signal: AbortSignal.timeout(12000),
    };
    const client = apiClient(
      process.env.QPQ_API_INTERNAL_URL ?? "http://localhost:8000",
    );
    let result;
    if (!id && request.method === "POST")
      result = await client.POST("/api/v1/projects", {
        ...opts,
        body: body as Definition,
      });
    else if (id && parts.length === 1 && request.method === "PUT")
      result = await client.PUT("/api/v1/projects/{project_id}", {
        ...opts,
        params: { path: { project_id: id } },
        body,
      });
    else if (id && parts[1] === "status" && request.method === "POST")
      result = await client.POST("/api/v1/projects/{project_id}/status", {
        ...opts,
        params: { path: { project_id: id } },
        body,
      });
    else return reply("Invalid request", 400);
    if (!result.response.ok) {
      const error = result.error as { detail?: unknown } | undefined;
      return reply(
        result.response.status === 422
          ? "Check field values, unique options and validation rules."
          : typeof error?.detail === "string"
            ? error.detail
            : "Collection service unavailable.",
        result.response.status,
      );
    }
    return Response.json(result.data, {
      status: result.response.status,
      headers: { "Cache-Control": "no-store", Vary: "Cookie" },
    });
  } catch {
    return reply("Collection service unavailable. Try again later.", 503);
  }
}
export const POST = transport;
export const PUT = transport;
