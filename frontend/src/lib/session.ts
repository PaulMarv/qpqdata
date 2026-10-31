import { cache } from "react";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { apiClient } from "./api";

export const currentUser = cache(async () => {
  const jar = await cookies();
  const headers = {
    Cookie: jar
      .getAll()
      .filter((c) => /^(?:__Host-)?qpq_(?:session|csrf)$/.test(c.name))
      .map((c) => c.name + "=" + c.value)
      .join("; "),
  };
  if (!headers.Cookie) return null;
  try {
    const { data } = await apiClient(
      process.env.QPQ_API_INTERNAL_URL ?? "http://localhost:8000",
    ).GET("/api/v1/auth/me", {
      headers,
      cache: "no-store",
      signal: AbortSignal.timeout(5000),
    });
    return data ?? null;
  } catch {
    return null;
  }
});

export async function requireUser() {
  const user = await currentUser();
  if (!user) redirect("/login");
  return user;
}
