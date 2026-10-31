import { notFound } from "next/navigation";
import EmailForm from "./email-form";
export const dynamic = "force-dynamic";
export default function DevelopmentEmail() {
  if (
    process.env.QPQ_ENVIRONMENT !== "development" ||
    process.env.QPQ_DEV_EMAIL_ENABLED !== "true"
  )
    notFound();
  return (
    <main id="main" className="mx-auto max-w-lg px-6 py-16">
      <h1 className="text-3xl font-semibold">Test email verification</h1>
      <p className="my-6 text-slate-700">
        Development only. Use student@university.test or another address at
        university.test. This confirms a local test mailbox; it does not create
        a login session or grant production eligibility.
      </p>
      <EmailForm />
      <p className="mt-8">
        <a
          className="underline"
          href="http://localhost:8025"
          target="_blank"
          rel="noreferrer"
        >
          Open local Mailpit inbox
        </a>
      </p>
    </main>
  );
}
