import { apiClient } from "../../../../lib/api";

export async function POST(
  request: Request,
  context: { params: Promise<{ action: string }> },
) {
  const reply = (detail: string, status: number) =>
    Response.json(
      { detail },
      { status, headers: { "Cache-Control": "no-store" } },
    );
  if (
    process.env.QPQ_ENVIRONMENT !== "development" ||
    process.env.QPQ_DEV_EMAIL_ENABLED !== "true"
  )
    return reply("Not found", 404);
  if (
    request.headers.get("origin") !==
    (process.env.QPQ_FRONTEND_URL ?? "http://localhost:3000").replace(/\/$/, "")
  )
    return reply("Origin rejected", 403);
  if (!request.headers.get("content-type")?.startsWith("application/json"))
    return reply("JSON required", 415);
  const { action } = await context.params;
  if (action !== "register" && action !== "verify")
    return reply("Not found", 404);
  try {
    const reader = request.body?.getReader();
    if (!reader) return reply("Invalid request", 400);
    const chunks: Uint8Array[] = [];
    let size = 0;
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > 2048) {
        await reader.cancel();
        return reply("Request too large", 413);
      }
      chunks.push(value);
    }
    const data = JSON.parse(Buffer.concat(chunks).toString("utf8"));
    const client = apiClient(
      process.env.QPQ_API_INTERNAL_URL ?? "http://localhost:8000",
    );
    let result;
    if (action === "register" && typeof data?.email === "string")
      result = await client.POST("/api/v1/dev-email/register", {
        body: { email: data.email },
        signal: AbortSignal.timeout(10000),
      });
    else if (action === "verify" && typeof data?.token === "string")
      result = await client.POST("/api/v1/dev-email/verify", {
        body: { token: data.token },
        signal: AbortSignal.timeout(10000),
      });
    else return reply("Invalid request", 400);
    if (!result.response.ok) {
      // Backend errors are sanitised, but forward only expected string details.
      const error = result.error as { detail?: unknown } | undefined;
      return reply(
        typeof error?.detail === "string"
          ? error.detail
          : "Verification request rejected",
        result.response.status,
      );
    }
    return Response.json(result.data, {
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return reply("Verification unavailable. Try again later.", 503);
  }
}
