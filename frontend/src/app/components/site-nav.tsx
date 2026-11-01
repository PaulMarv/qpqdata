"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export default function SiteNav() {
  const pathname = usePathname();
  return (
    <nav aria-label="Main navigation" className="site-nav">
      {[
        { href: "/projects", label: "Explore" },
        { href: "/datasets", label: "Datasets" },
      ].map(({ href, label }) => (
        <Link
          key={href}
          href={href}
          className="site-nav-link"
          aria-current={
            pathname === href || pathname.startsWith(href + "/")
              ? "page"
              : undefined
          }
        >
          {label}
        </Link>
      ))}
    </nav>
  );
}
