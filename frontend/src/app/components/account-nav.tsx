"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

type User = { email: string; display_name: string };
export default function AccountNav({ user }: { user: User | null }) {
  const router = useRouter();
  const [session, setSession] = useState({ source: user, value: user });
  const activeUser = session.source === user ? session.value : user;
  const sessionGeneration = useRef(0);
  const signingOut = useRef(false);
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState(false);
  const menu = useRef<HTMLDetailsElement>(null);
  const trigger = useRef<HTMLElement>(null);
  const pathname = usePathname();
  useEffect(() => {
    let disposed = false;
    let checking = false;
    const controller = new AbortController();
    async function checkSession() {
      if (
        checking ||
        signingOut.current ||
        document.visibilityState === "hidden"
      )
        return;
      const generation = sessionGeneration.current;
      checking = true;
      try {
        const response = await fetch("/api/auth/me", {
          cache: "no-store",
          credentials: "same-origin",
          signal: controller.signal,
        });
        if (disposed || generation !== sessionGeneration.current) return;
        if (response.status === 401 || response.status === 403) {
          setSession({ source: user, value: null });
        } else if (response.ok) {
          const account: unknown = await response.json();
          if (
            !disposed &&
            generation === sessionGeneration.current &&
            account &&
            typeof account === "object" &&
            "email" in account &&
            typeof account.email === "string" &&
            "display_name" in account &&
            typeof account.display_name === "string"
          )
            setSession({
              source: user,
              value: {
                email: account.email,
                display_name: account.display_name,
              },
            });
        }
      } catch {
        // A network failure does not establish that the session has expired.
      } finally {
        checking = false;
      }
    }
    void checkSession();
    const timer = window.setInterval(checkSession, 30000);
    window.addEventListener("focus", checkSession);
    document.addEventListener("visibilitychange", checkSession);
    return () => {
      disposed = true;
      controller.abort();
      window.clearInterval(timer);
      window.removeEventListener("focus", checkSession);
      document.removeEventListener("visibilitychange", checkSession);
    };
  }, [pathname, user]);
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
  }, [pathname, activeUser?.email]);
  if (!activeUser)
    return (
      <nav aria-label="Account" className="flex items-center gap-4 sm:gap-8">
        <Link
          href="/login"
          aria-current={pathname === "/login" ? "page" : undefined}
        >
          Log in
        </Link>
        <Link
          href="/signup"
          aria-current={pathname === "/signup" ? "page" : undefined}
        >
          Sign up
        </Link>
      </nav>
    );
  const initials = (activeUser.display_name || activeUser.email)
    .slice(0, 2)
    .toUpperCase();
  async function logout() {
    setPending(true);
    signingOut.current = true;
    sessionGeneration.current += 1;
    try {
      const response = await fetch("/api/auth/logout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      if (response.ok || response.status === 401) {
        setSession({ source: user, value: null });
        router.replace("/");
        router.refresh();
      } else setMessage("Sign out failed. Try again.");
    } catch {
      setMessage("Sign out failed. Try again.");
    } finally {
      signingOut.current = false;
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
            aria-current={
              pathname === url || pathname.startsWith(url + "/")
                ? "page"
                : undefined
            }
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
