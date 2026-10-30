import createClient from "openapi-fetch";
import type { paths } from "./api-schema";

export function apiClient(baseUrl: string, fetcher: typeof fetch = fetch) {
  return createClient<paths>({ baseUrl, fetch: fetcher });
}

export async function getReadiness(baseUrl: string): Promise<boolean> {
  try {
    const { data, error } = await apiClient(baseUrl).GET(
      "/api/v1/health/ready",
      {
        signal: AbortSignal.timeout(3000),
        cache: "no-store",
      },
    );
    return !error && data?.status === "ok";
  } catch {
    return false;
  }
}
