"use client";
import { useState, type FormEvent } from "react";
export default function EmailForm() {
  const [email, setEmail] = useState("student@university.test");
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setMessage("");
    try {
      const response = await fetch("/api/dev-email/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const result = await response.json();
      setMessage(
        response.ok
          ? result.message
          : typeof result.detail === "string"
            ? result.detail
            : "Registration unavailable.",
      );
    } catch {
      setMessage("Registration unavailable. Try again later.");
    } finally {
      setPending(false);
    }
  }
  return (
    <form onSubmit={submit}>
      <label className="block font-semibold" htmlFor="test-email">
        Test email address
      </label>
      <input
        id="test-email"
        type="email"
        autoComplete="email"
        required
        maxLength={254}
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        className="my-3 w-full rounded border border-slate-500 bg-white p-3"
      />
      <button
        disabled={pending}
        className="rounded bg-teal-800 px-5 py-3 font-semibold text-white disabled:opacity-60"
      >
        {pending ? "Sending…" : "Register test account"}
      </button>
      <p role="status" className="mt-5">
        {message}
      </p>
    </form>
  );
}
