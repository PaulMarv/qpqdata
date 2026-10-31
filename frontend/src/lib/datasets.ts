import type { components } from "./api-schema";
export type Dataset = components["schemas"]["DatasetView"];
export type ExportConsent = components["schemas"]["ConsentView"];
export async function datasetAction<T>(
  path: string,
  body: unknown = {},
): Promise<T> {
  const r = await fetch("/api/datasets/" + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (r.status === 204) return undefined as T;
  const data = await r.json();
  if (!r.ok)
    throw new Error(
      typeof data.detail === "string" ? data.detail : "Dataset request failed.",
    );
  return data as T;
}
