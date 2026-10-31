import { requireUser } from "../../../lib/session";
export default async function Wallet() {
  const user = await requireUser();
  return (
    <main id="main" className="mx-auto max-w-lg px-6 py-16">
      <h1 className="text-3xl font-semibold">QPQ Wallet</h1>
      <p className="my-8 text-4xl font-semibold">{user.credit_balance} QC</p>
      <p>
        Credits are calculated from your ledger. Eligible verified accounts
        receive a one-time 50 QC welcome grant.
      </p>
    </main>
  );
}
