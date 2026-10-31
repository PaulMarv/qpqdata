"use client";
import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
export default function ProfileForm({ initialName }: { initialName: string }) {
  const [name, setName] = useState(initialName);
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState(false);
  const router = useRouter();
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    try {
      const r = await fetch("/api/auth/profile", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ display_name: name }),
      });
      setMessage(
        r.ok
          ? "Profile updated."
          : "Profile could not be updated. Try signing in again.",
      );
      if (r.ok) router.refresh();
    } catch {
      setMessage("Account service unavailable.");
    } finally {
      setPending(false);
    }
  }
  return (
    <form onSubmit={save} className="mt-6 space-y-4">
      <label htmlFor="profile-name" className="block">
        Display name
      </label>
      <input
        id="profile-name"
        autoComplete="name"
        required
        maxLength={100}
        value={name}
        onChange={(e) => setName(e.target.value)}
        className="w-full rounded border p-3"
      />
      <button
        disabled={pending}
        className="rounded bg-teal-800 px-5 py-3 text-white"
      >
        {pending ? "Saving…" : "Save profile"}
      </button>
      <p role="status">{message}</p>
    </form>
  );
}
