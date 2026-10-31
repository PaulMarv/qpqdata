import { requireUser } from "../../../lib/session";
import ProfileForm from "../../components/profile-form";
export default async function ProfilePage() {
  const user = await requireUser();
  return (
    <main id="main" className="mx-auto max-w-lg px-6 py-16">
      <h1 className="text-3xl font-semibold">My Profile</h1>
      <p className="mt-6">Verified email: {user.email}</p>
      <ProfileForm initialName={user.display_name} />
    </main>
  );
}
