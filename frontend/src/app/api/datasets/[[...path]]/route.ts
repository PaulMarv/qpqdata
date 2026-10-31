export const runtime = "nodejs";
async function transport(
  request: Request,
  context: { params: Promise<{ path?: string[] }> },
) {
  const parts = (await context.params).path ?? [],
    uuid = /^[0-9a-f-]{36}$/;
  const reply = (detail: string, status: number) =>
    Response.json(
      { detail },
      { status, headers: { "Cache-Control": "no-store" } },
    );
  const origin = (
    process.env.QPQ_FRONTEND_URL ?? "http://localhost:3000"
  ).replace(/\/$/, "");
  if (request.method !== "GET" && request.headers.get("origin") !== origin)
    return reply("Request rejected.", 403);
  let route: string | undefined;
  if (!parts.length && request.method === "GET")
    route = "/datasets" + new URL(request.url).search;
  if (
    ["start", "collection", "consent", "withdraw-consent"].includes(parts[0]) &&
    parts.length === 2 &&
    uuid.test(parts[1])
  ) {
    route =
      parts[0] === "start" || parts[0] === "collection"
        ? `/projects/${parts[1]}/dataset`
        : `/submissions/${parts[1]}/${parts[0] === "consent" ? "export-consent" : "withdraw-export"}`;
  }
  if (uuid.test(parts[0] ?? "")) {
    if (parts.length === 1) route = `/datasets/${parts[0]}`;
    if (
      parts.length === 2 &&
      ["review", "versions", "withdraw", "reports"].includes(parts[1])
    )
      route = `/datasets/${parts[0]}/${parts[1]}`;
    if (
      parts.length === 3 &&
      ["authorise", "withdraw-image"].includes(parts[1]) &&
      uuid.test(parts[2])
    )
      route = `/datasets/${parts[0]}/images/${parts[2]}/${parts[1] === "authorise" ? "authorise" : "withdraw"}`;
    if (
      parts.length === 4 &&
      parts[1] === "versions" &&
      /^[1-9][0-9]{0,8}$/.test(parts[2]) &&
      ["prepare", "download"].includes(parts[3])
    )
      route = `/datasets/${parts[0]}/versions/${parts[2]}/${parts[3]}`;
  }
  if (!route) return reply("Not found", 404);
  const download = parts[3] === "download";
  if (download && request.method !== "GET") return reply("Not found", 404);
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
  let body: string | undefined;
  try {
    if (request.method !== "GET") {
      if (!request.headers.get("content-type")?.startsWith("application/json"))
        return reply("JSON required", 415);
      const reader = request.body?.getReader(),
        chunks: Uint8Array[] = [];
      let size = 0;
      if (reader)
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          size += value.byteLength;
          if (size > 8192) {
            await reader.cancel();
            return reply("Request too large", 413);
          }
          chunks.push(value);
        }
      body = Buffer.concat(chunks).toString("utf8") || "{}";
      JSON.parse(body);
    }
    const response = await fetch(
      (process.env.QPQ_API_INTERNAL_URL ?? "http://localhost:8000") +
        "/api/v1" +
        route,
      {
        method: request.method,
        headers: {
          Cookie: cookie,
          Origin: origin,
          "Content-Type": "application/json",
          ...(csrf ? { "X-CSRF-Token": csrf } : {}),
        },
        body,
        cache: "no-store",
        signal: AbortSignal.timeout(download ? 15 * 60 * 1000 : 15000),
      },
    );
    const headers: Record<string, string> = {
      "Cache-Control": "no-store",
      Vary: "Cookie",
      "X-Content-Type-Options": "nosniff",
      "Content-Type":
        response.headers.get("content-type") ?? "application/json",
    };
    if (download && response.ok) {
      headers["Content-Disposition"] =
        `attachment; filename="qpqdata-${parts[0]}-v${parts[2]}.zip"`;
      const size = response.headers.get("content-length");
      if (size) headers["Content-Length"] = size;
    }
    return new Response(response.body, { status: response.status, headers });
  } catch {
    return reply("Dataset service unavailable. Retry safely.", 503);
  }
}
export const GET = transport;
export const POST = transport;
