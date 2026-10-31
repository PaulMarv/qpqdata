import Link from "next/link";
import LoginForm from "../components/login-form";
import { currentUser } from "../../lib/session";
import { redirect } from "next/navigation";
export const dynamic = "force-dynamic";
export default async function Page() {
  if (await currentUser()) redirect("/profile");
  return (
    <main id="main" className="mx-auto max-w-lg px-6 py-16">
      <h1 className="mb-6 text-3xl font-semibold">Log in</h1>
      <p className="mb-6">
        Use your approved school or work email. No password is needed.
      </p>
      <LoginForm signup={false} />
      <p className="mt-6">
        <Link className="underline" href="/signup">
          New to QPQData? Sign up
        </Link>
      </p>
    </main>
  );
}
