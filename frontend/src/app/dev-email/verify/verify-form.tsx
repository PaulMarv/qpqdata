"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
export default function VerifyForm({
  authentication = false,
}: {
  authentication?: boolean;
}) {
  const router = useRouter();
  const tokenRef = useRef<string | null>(null);
  const [done, setDone] = useState(false);
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState(false);
  useEffect(() => {
    const candidate = new URLSearchParams(window.location.hash.slice(1)).get(
      "token",
    );
    window.history.replaceState(
      window.history.state,
      "",
      window.location.pathname,
    );
    if (candidate) tokenRef.current = candidate;
  }, []);
  async function verify() {
    const token = tokenRef.current;
    if (!token) {
      setMessage("Link invalid or expired. Request a new verification email.");
      return;
    }
    setPending(true);
    try {
      const response = await fetch(
        authentication ? "/api/auth/verify" : "/api/dev-email/verify",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token }),
        },
      );
      const result = await response.json();
      if (authentication && response.ok && result.status === "authenticated") {
        router.replace("/profile");
        router.refresh();
        return;
      }
      if (authentication && response.ok && result.status === "pending_review") {
        setMessage(
          "Email verified. Organisation membership review is required before login.",
        );
        tokenRef.current = null;
        setDone(true);
        return;
      }
      setMessage(
        response.ok
          ? result.message
          : typeof result.detail === "string"
            ? result.detail
            : "Link invalid or expired.",
      );
      tokenRef.current = null;
      setDone(true);
    } catch {
      setMessage("Verification unavailable. Try again later.");
    } finally {
      setPending(false);
    }
  }
  return (
    <div>
      <button
        onClick={verify}
        disabled={done || pending}
        className="rounded bg-blue-700 px-5 py-3 font-semibold text-white disabled:opacity-60"
      >
        {pending ? "Verifying…" : "Verify email"}
      </button>
      <p role="status" className="my-5">
        {message || "Confirm using the verification link from Mailpit."}
      </p>
      <Link
        className="underline"
        href={authentication ? "/login" : "/dev-email"}
      >
        Request another email
      </Link>
    </div>
  );
}
