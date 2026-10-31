import Link from "next/link";
import LoginForm from "../components/login-form";
import { currentUser } from "../../lib/session";
import { redirect } from "next/navigation";
export const dynamic = "force-dynamic";
export default async function Page() {
  if (await currentUser()) redirect("/profile");
  return (
    <main id="main" className="mx-auto max-w-lg px-6 py-16">
      <h1 className="mb-6 text-3xl font-semibold">Sign up</h1>
      <p className="mb-6">
        Use your approved school or work email. No password is needed. Eligible
        verified accounts receive 50 QC once.
      </p>
      <LoginForm signup={true} />
      <p className="mt-6">
        <Link className="underline" href="/login">
          Already registered? Log in
        </Link>
      </p>
    </main>
  );
}
