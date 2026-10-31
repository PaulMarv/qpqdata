"use client";
import { useState, type FormEvent } from "react";
export default function LoginForm({ signup = false }: { signup?: boolean }) {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    try {
      const response = await fetch("/api/auth/request-link", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          intent: signup ? "signup" : "login",
          display_name: name,
        }),
      });
      setMessage(
        response.ok
          ? "If this account can continue, a link has been sent. Check your email and open the link in this browser within 10 minutes."
          : "Request unavailable. Please check your address or try again later.",
      );
    } catch {
      setMessage("Account service unavailable. Try again later.");
    } finally {
      setPending(false);
    }
  }
  return (
    <form onSubmit={submit} className="space-y-4">
      {signup && (
        <div>
          <label htmlFor="name" className="block">
            Your name
          </label>
          <input
            id="name"
            autoComplete="name"
            maxLength={100}
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="mt-2 w-full rounded border p-3"
          />
        </div>
      )}
      <div>
        <label htmlFor="email" className="block">
          School or work email
        </label>
        <input
          id="email"
          type="email"
          autoComplete="email"
          maxLength={254}
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="mt-2 w-full rounded border p-3"
        />
      </div>
      <button
        disabled={pending}
        className="rounded bg-teal-800 px-5 py-3 text-white disabled:opacity-60"
      >
        {pending
          ? "Sending…"
          : signup
            ? "Send verification link"
            : "Send login link"}
      </button>
      <p role="status">{message}</p>
    </form>
  );
}
