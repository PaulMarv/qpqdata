import { apiClient } from "../../../../lib/api";

async function transport(
  request: Request,
  context: { params: Promise<{ action: string }> },
) {
  const reply = (detail: string, status: number) =>
    Response.json(
      { detail },
      { status, headers: { "Cache-Control": "no-store" } },
    );
  const { action } = await context.params;
  if (!["request-link", "verify", "me", "profile", "logout"].includes(action))
    return reply("Not found", 404);
  if (
    request.method !== "GET" &&
    request.headers.get("origin") !==
      (process.env.QPQ_FRONTEND_URL ?? "http://localhost:3000").replace(
        /\/$/,
        "",
      )
  )
    return reply("Request rejected.", 403);
  if (
    request.method !== "GET" &&
    !request.headers.get("content-type")?.startsWith("application/json")
  )
    return reply("JSON required", 415);
  try {
    const cookie = (request.headers.get("cookie") ?? "")
      .split(";")
      .map((s) => s.trim())
      .filter((s) => /^(?:__Host-)?qpq_(?:session|csrf|login_nonce)=/.test(s))
      .join("; ");
    const csrf = cookie
      .split(";")
      .map((s) => s.trim())
      .find((s) => /^(?:__Host-)?qpq_csrf=/.test(s))
      ?.split("=")[1];
    const headers: Record<string, string> = {
      Cookie: cookie,
      Origin: (process.env.QPQ_FRONTEND_URL ?? "http://localhost:3000").replace(
        /\/$/,
        "",
      ),
    };
    if (csrf) headers["X-CSRF-Token"] = csrf;
    let body: Record<string, unknown> = {};
    if (request.method !== "GET") {
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
      body = JSON.parse(Buffer.concat(chunks).toString("utf8"));
    }
    const client = apiClient(
      process.env.QPQ_API_INTERNAL_URL ?? "http://localhost:8000",
    );
    const opts = {
      headers,
      cache: "no-store" as const,
      signal: AbortSignal.timeout(12000),
    };
    let result;
    if (
      action === "request-link" &&
      request.method === "POST" &&
      typeof body.email === "string" &&
      (body.intent === "signup" || body.intent === "login")
    )
      result = await client.POST("/api/v1/auth/request-link", {
        ...opts,
        body: {
          email: body.email,
          intent: body.intent,
          display_name:
            typeof body.display_name === "string" ? body.display_name : "",
        },
      });
    else if (
      action === "verify" &&
      request.method === "POST" &&
      typeof body.token === "string"
    )
      result = await client.POST("/api/v1/auth/verify", {
        ...opts,
        body: { token: body.token },
      });
    else if (action === "me" && request.method === "GET")
      result = await client.GET("/api/v1/auth/me", opts);
    else if (
      action === "profile" &&
      request.method === "PATCH" &&
      typeof body.display_name === "string"
    )
      result = await client.PATCH("/api/v1/auth/profile", {
        ...opts,
        body: { display_name: body.display_name },
      });
    else if (action === "logout" && request.method === "POST")
      result = await client.POST("/api/v1/auth/logout", opts);
    else return reply("Invalid request", 400);
    const response = Response.json(
      result.response.ok
        ? result.data
        : {
            detail:
              "Request could not be completed. Check your link or sign in again.",
          },
      {
        status: result.response.status,
        headers: { "Cache-Control": "no-store", Vary: "Cookie" },
      },
    );
    for (const value of result.response.headers.getSetCookie())
      response.headers.append("Set-Cookie", value);
    // An expired session cannot reach logout's normal deletion path. Clear local
    // cookies too; the server-side record is already unusable.
    if (action === "logout" && [401, 403].includes(result.response.status)) {
      for (const name of [
        "qpq_session",
        "qpq_csrf",
        "__Host-qpq_session",
        "__Host-qpq_csrf",
      ])
        response.headers.append(
          "Set-Cookie",
          name +
            "=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0" +
            (name.startsWith("__Host-") ? "; Secure" : ""),
        );
    }
    return response;
  } catch {
    return reply("Account service unavailable. Try again later.", 503);
  }
}
export const GET = transport;
export const POST = transport;
export const PATCH = transport;
