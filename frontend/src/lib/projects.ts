import type { components } from "./api-schema";
export type Definition = components["schemas"]["ProjectDefinition"];
export type Project = components["schemas"]["ProjectView"];
export type ProjectPage = components["schemas"]["ProjectPage"];
export type Question = components["schemas"]["Question"];
export const categories = [
  "science",
  "education",
  "environment",
  "health",
  "technology",
  "society",
  "other",
] as const;
export const blankDefinition = (): Definition => ({
  schema_version: 1,
  mode: "crowdsourced",
  label_title: "Image label",
  name: "",
  description: "",
  research_purpose: "",
  category: "other",
  image_count: 20,
  reward_per_image: 1,
  instructions: "",
  accepted_content: "",
  prohibited_content: "",
  min_width: 640,
  min_height: 640,
  allowed_formats: ["JPEG", "PNG"],
  closing_date: null,
  licence: "",
  reuse_terms: "",
  keywords: [],
  labels: [],
  criteria: { schema_version: 1, questions: [] },
});
export const key = (prefix: string) =>
  prefix + "_" + crypto.randomUUID().replaceAll("-", "");
export function budget(d: Definition) {
  return d.mode === "personal"
    ? 0
    : (d.image_count ?? 20) * (d.reward_per_image ?? 1);
}
export async function projectMutation(
  path: string,
  method: "POST" | "PUT",
  body: unknown,
): Promise<Project> {
  const response = await fetch("/api/projects" + path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const value = await response.json();
  if (!response.ok)
    throw new Error(
      typeof value.detail === "string"
        ? value.detail
        : "Check the field values and try again.",
    );
  return value as Project;
}
