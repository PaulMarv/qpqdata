import Link from "next/link";
import AccountNav from "./components/account-nav";
import { currentUser } from "../lib/session";
import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
const bodyFont = localFont({
  src: "./fonts/Manrope.ttf",
  variable: "--font-body",
  display: "swap",
  weight: "200 800",
});
const headingFont = localFont({
  src: "./fonts/SpaceGrotesk.ttf",
  variable: "--font-heading",
  display: "swap",
  weight: "300 700",
});
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
      <body className={`${bodyFont.variable} ${headingFont.variable}`}>
        <a className="skip-link" href="#main">
          Skip to content
        </a>
        <header className="site-header mx-auto flex max-w-6xl items-center justify-between px-5 py-5 sm:px-10">
          <Link className="brand text-xl font-bold" href="/">
            QPQ<span className="brand-accent">Data</span>
          </Link>
          <div className="flex items-center gap-4 sm:gap-8">
            <Link className="text-sm font-semibold" href="/projects">
              Explore
            </Link>
            <AccountNav user={user} />
          </div>
        </header>
        {children}
      </body>
    </html>
  );
}
