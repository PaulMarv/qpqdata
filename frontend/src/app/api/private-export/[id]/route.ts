import { cookies } from "next/headers";
export const runtime = "nodejs";
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  if (!/^[0-9a-f-]{36}$/.test(id)) return new Response(null, { status: 404 });
  const jar = await cookies();
  const cookie = jar
    .getAll()
    .filter((c) => /^(?:__Host-)?qpq_(?:session|csrf)$/.test(c.name))
    .map((c) => c.name + "=" + c.value)
    .join("; ");
  try {
    const response = await fetch(
      (process.env.QPQ_API_INTERNAL_URL ?? "http://localhost:8000") +
        `/api/v1/projects/${id}/private-export`,
      {
        headers: { Cookie: cookie },
        cache: "no-store",
        signal: AbortSignal.timeout(180000),
      },
    );
    const headers: Record<string, string> = {
      "Cache-Control": "no-store",
      Vary: "Cookie",
      "Content-Type":
        response.headers.get("content-type") ?? "application/json",
      "X-Content-Type-Options": "nosniff",
    };
    if (response.ok) {
      headers["Content-Disposition"] =
        `attachment; filename="qpqdata-private-${id}.zip"`;
      const size = response.headers.get("content-length");
      if (size) headers["Content-Length"] = size;
    }
    return new Response(response.body, { status: response.status, headers });
  } catch {
    return Response.json(
      { detail: "Private export unavailable. Try again." },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }
}
