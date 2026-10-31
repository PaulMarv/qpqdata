import { requireUser } from "../../lib/session";
export default async function AccountLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  await requireUser();
  return children;
}
