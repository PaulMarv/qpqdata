"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

type User = { email: string; display_name: string };
export default function AccountNav({ user }: { user: User | null }) {
  const router = useRouter();
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState(false);
  const menu = useRef<HTMLDetailsElement>(null);
  const trigger = useRef<HTMLElement>(null);
  const pathname = usePathname();
  useEffect(() => {
    function outside(event: PointerEvent) {
      if (menu.current && !menu.current.contains(event.target as Node))
        menu.current.open = false;
    }
    function escape(event: KeyboardEvent) {
      if (event.key === "Escape" && menu.current?.open) {
        menu.current.open = false;
        trigger.current?.focus();
      }
    }
    function focusOutside(event: FocusEvent) {
      if (menu.current && !menu.current.contains(event.target as Node))
        menu.current.open = false;
    }
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", escape);
    document.addEventListener("focusin", focusOutside);
    return () => {
      document.removeEventListener("pointerdown", outside);
      document.removeEventListener("keydown", escape);
      document.removeEventListener("focusin", focusOutside);
    };
  }, []);
  useEffect(() => {
    if (menu.current) menu.current.open = false;
  }, [pathname, user]);
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
    <details ref={menu} className="profile-dropdown relative">
      <summary
        ref={trigger}
        aria-label="Open profile menu"
        className="profile-avatar flex h-11 w-11 cursor-pointer list-none items-center justify-center rounded-full font-semibold text-white"
      >
        {initials}
      </summary>
      <nav
        aria-label="Profile menu"
        className="profile-popover absolute right-0 z-20 mt-3 w-64 bg-white p-2"
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
            onClick={() => {
              if (menu.current) menu.current.open = false;
            }}
            className="block rounded-xl p-3"
          >
            {label}
          </Link>
        ))}
        <button
          onClick={logout}
          disabled={pending}
          className="profile-signout w-full rounded-xl p-3 text-left"
        >
          {pending ? "Signing out…" : "Sign Out"}
        </button>
        <p role="status">{message}</p>
      </nav>
    </details>
  );
}
