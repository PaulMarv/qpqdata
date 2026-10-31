import VerifyForm from "../dev-email/verify/verify-form";
export const metadata = {
  robots: { index: false, follow: false },
  referrer: "no-referrer" as const,
};
export default function Page() {
  return (
    <main id="main" className="mx-auto max-w-lg px-6 py-16">
      <h1 className="text-3xl font-semibold">Confirm your email</h1>
      <p className="my-6">
        Use the same browser that requested this single-use link. Confirm below
        to continue.
      </p>
      <VerifyForm authentication />
    </main>
  );
}
