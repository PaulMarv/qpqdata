import { cookies } from "next/headers";
import { apiClient } from "./api";
export async function projectApi() {
  const jar = await cookies();
  const Cookie = jar
    .getAll()
    .filter((c) => /^(?:__Host-)?qpq_(?:session|csrf)$/.test(c.name))
    .map((c) => c.name + "=" + c.value)
    .join("; ");
  return {
    client: apiClient(
      process.env.QPQ_API_INTERNAL_URL ?? "http://localhost:8000",
    ),
    options: {
      headers: { Cookie },
      cache: "no-store" as const,
      signal: AbortSignal.timeout(8000),
    },
  };
}
