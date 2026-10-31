import { requireUser } from "../../../lib/session";
export default async function Wallet() {
  const user = await requireUser();
  return (
    <main id="main" className="mx-auto max-w-lg px-6 py-16">
      <h1 className="text-3xl font-semibold">QPQ Wallet</h1>
      <p className="my-8 text-4xl font-semibold">
        {user.credit_balance} QC available
      </p>
      <p className="mb-6">
        {user.reserved_credits} QC reserved ·{" "}
        {user.credit_balance + user.reserved_credits} QC total
      </p>
      <p>
        Published collections reserve QC through the ledger. Pausing holds the
        reservation; closing releases it. Credits are calculated from your
        ledger. Eligible verified accounts receive a one-time 50 QC welcome
        grant.
      </p>
    </main>
  );
}
