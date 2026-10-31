"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

type User = { email: string; display_name: string };
export default function AccountNav({ user }: { user: User | null }) {
  const router = useRouter();
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState(false);
  if (!user)
    return (
      <nav aria-label="Account" className="flex gap-5">
        <Link href="/login">Log in</Link>
        <Link href="/signup">Sign up</Link>
      </nav>
    );
  const initials = (user.display_name || user.email).slice(0, 2).toUpperCase();
  async function logout() {
    setPending(true);
    try {
      const response = await fetch("/api/auth/logout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      if (response.ok || response.status === 401) {
        router.replace("/");
        router.refresh();
      } else setMessage("Sign out failed. Try again.");
    } catch {
      setMessage("Sign out failed. Try again.");
    } finally {
      setPending(false);
    }
  }
  return (
    <details className="relative">
      <summary
        aria-label="Open profile menu"
        className="flex h-11 w-11 cursor-pointer list-none items-center justify-center rounded-full bg-teal-800 font-semibold text-white"
      >
        {initials}
      </summary>
      <nav
        aria-label="Profile menu"
        className="absolute right-0 z-20 mt-3 w-56 rounded-lg border border-slate-200 bg-white p-4 shadow-lg"
      >
        {[
          ["My Profile", "/profile"],
          ["My Collections", "/collections"],
          ["My Submissions", "/submissions"],
          ["QPQ Wallet", "/wallet"],
        ].map(([label, url]) => (
          <Link
            key={url}
            href={url}
            className="block rounded p-3 hover:bg-teal-50"
          >
            {label}
          </Link>
        ))}
        <button
          onClick={logout}
          disabled={pending}
          className="w-full rounded p-3 text-left hover:bg-teal-50"
        >
          {pending ? "Signing out…" : "Sign Out"}
        </button>
        <p role="status">{message}</p>
      </nav>
    </details>
  );
}
