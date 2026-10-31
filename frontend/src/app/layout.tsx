import Link from "next/link";
import AccountNav from "./components/account-nav";
import { currentUser } from "../lib/session";
import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "QPQData — Images with purpose",
  description: "A foundation for community-powered image datasets.",
};
export default async function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const user = await currentUser();
  return (
    <html lang="en">
      <body>
        <a className="skip-link" href="#main">
          Skip to content
        </a>
        <header className="mx-auto flex max-w-6xl items-center justify-between border-b border-slate-200 px-6 py-6 sm:px-10">
          <Link className="text-xl font-bold" href="/">
            QPQ<span className="text-teal-700">Data</span>
          </Link>
          <AccountNav user={user} />
        </header>
        {children}
      </body>
    </html>
  );
}
