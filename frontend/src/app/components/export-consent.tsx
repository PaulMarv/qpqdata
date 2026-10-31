"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  datasetAction,
  type Dataset,
  type ExportConsent,
} from "../../lib/datasets";
export default function ExportConsentForm({ id }: { id: string }) {
  const [consent, setConsent] = useState<ExportConsent | null>(null),
    [dataset, setDataset] = useState<Dataset | null>(null),
    [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false);
  const router = useRouter();
  useEffect(() => {
    const controller = new AbortController();
    (async () => {
      try {
        const r = await fetch("/api/datasets/consent/" + id, {
          signal: controller.signal,
          cache: "no-store",
        });
        if (!r.ok) return;
        const c = (await r.json()) as ExportConsent;
        setConsent(c);
        if (c.publication_id) {
          const d = await fetch("/api/datasets/" + c.publication_id, {
            signal: controller.signal,
            cache: "no-store",
          });
          if (d.ok) setDataset((await d.json()) as Dataset);
        }
      } catch {}
    })();
    return () => controller.abort();
  }, [id]);
  if (!consent?.publication_id || !dataset) return null;
  async function submit(alias: string, withdraw = false) {
    if (!withdraw && !/^[\p{L}\p{N}_ .'\-]*$/u.test(alias)) {
      setMessage("Use a public pseudonym, not an email or URL.");
      return;
    }
    setBusy(true);
    try {
      const c = await datasetAction<ExportConsent>(
        (withdraw ? "withdraw-consent/" : "consent/") + id,
        withdraw
          ? {}
          : {
              publication_id: consent?.publication_id,
              agree_public_distribution: true,
              public_attribution: alias,
            },
      );
      setConsent(c);
      setMessage(
        withdraw
          ? "Further dataset distribution revoked. Already downloaded copies cannot be recalled. Earned QC is retained."
          : "Public distribution consent recorded; owner export review is still required.",
      );
      router.refresh();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Export consent failed.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="project-inset">
      <h3>Optional public dataset distribution</h3>
      <p>
        Licence: {dataset.licence} · {dataset.reuse_terms}
      </p>
      <p>
        Public fields:{" "}
        {(dataset.criteria.questions ?? []).map((q) => q.title).join(", ") ||
          "image label only"}
        . Text answers remain private. This opt-in does not change earned QC.
      </p>
      {consent.withdrawn ? (
        <p>Further distribution permission withdrawn.</p>
      ) : consent.id ? (
        <>
          <p>
            {consent.authorised
              ? "Owner authorised for export."
              : "Waiting for owner distribution review."}
          </p>
          <button
            className="project-link"
            disabled={busy}
            onClick={() => submit("", true)}
          >
            Withdraw further dataset distribution
          </button>
        </>
      ) : (
        <form
          className="project-form"
          onSubmit={(e) => {
            e.preventDefault();
            submit(String(new FormData(e.currentTarget).get("alias") || ""));
          }}
        >
          <label>
            Public attribution pseudonym{" "}
            {dataset.licence !== "CC0-1.0" ? "(required)" : "(optional)"}
            <input
              name="alias"
              required={dataset.licence !== "CC0-1.0"}
              maxLength={80}
              autoComplete="off"
            />
          </label>
          <p>
            Use a public pseudonym, never your email address or private account
            details.
          </p>
          <label className="dataset-check">
            <input type="checkbox" required />I permit worldwide public
            distribution of this image and the selected labels under the
            recorded licence, confirm I have those rights, and understand
            downloaded copies cannot be recalled. Open licence grants already
            made may remain effective.
          </label>
          <button className="project-button secondary" disabled={busy}>
            Allow public dataset distribution
          </button>
        </form>
      )}
      <p role="status">{message}</p>
    </section>
  );
}
