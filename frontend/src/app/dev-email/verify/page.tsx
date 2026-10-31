import { notFound } from "next/navigation";
import VerifyForm from "./verify-form";
export const dynamic = "force-dynamic";
export const metadata = {
  robots: { index: false, follow: false },
  referrer: "no-referrer" as const,
};
export default function VerifyPage() {
  if (
    process.env.QPQ_ENVIRONMENT !== "development" ||
    process.env.QPQ_DEV_EMAIL_ENABLED !== "true"
  )
    notFound();
  return (
    <main id="main" className="mx-auto max-w-lg px-6 py-16">
      <h1 className="text-3xl font-semibold">Verify your test email</h1>
      <p className="my-6">
        Confirm below to activate your development account. Opening this page
        alone does not consume the link.
      </p>
      <VerifyForm />
    </main>
  );
}
