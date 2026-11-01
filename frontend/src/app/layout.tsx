import Brand from "./components/brand";
import AccountNav from "./components/account-nav";
import SiteNav from "./components/site-nav";
import { currentUser } from "../lib/session";
import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import "./styles/surfaces.css";
import "./styles/cards.css";
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
  description:
    "Capture and label personal image collections, contribute to research projects and download published public datasets for free.",
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
        <header className="site-header">
          <div className="site-header-inner">
            <Brand />
            <div className="flex flex-wrap items-center gap-3 sm:gap-5">
              <SiteNav />
              <AccountNav user={user} />
            </div>
          </div>
        </header>
        {children}
      </body>
    </html>
  );
}
