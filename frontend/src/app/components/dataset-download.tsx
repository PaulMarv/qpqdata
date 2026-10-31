"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { datasetAction, type Dataset } from "../../lib/datasets";
export default function DatasetDownload({ dataset: d }: { dataset: Dataset }) {
  const [ack, setAck] = useState(false),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState("");
  const router = useRouter();
  async function prepare(version: number) {
    setBusy(true);
    setMessage("");
    try {
      await datasetAction(`${d.id}/versions/${version}/prepare`);
      setMessage(
        "ZIP preparation queued. Refresh availability shortly; downloading costs 0 QC.",
      );
      router.refresh();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Preparation failed.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="project-panel project-form">
      <h2>Download · Free · 0 QC</h2>
      <p>
        Licence:{" "}
        <a
          className="project-link"
          href={d.licence_url}
          target="_blank"
          rel="noreferrer"
        >
          {d.licence}
        </a>
      </p>
      <p>{d.reuse_terms}</p>
      <p>
        Retain per-image attribution and the dataset/version reference. Observe
        ShareAlike where applicable and identify changes. Previously downloaded
        copies cannot be remotely revoked.
      </p>
      <label className="dataset-check">
        <input
          type="checkbox"
          checked={ack}
          onChange={(e) => setAck(e.target.checked)}
        />
        I have read the licence and permitted-use terms.
      </label>
      {!d.versions.length && <p>No export version has been published yet.</p>}
      {d.versions.map((v) => (
        <div key={v.version} className="project-inset">
          <p>
            Version {v.version} · {v.image_count} images ·{" "}
            {v.revoked ? "Revoked" : v.state}
          </p>
          {v.revoked ? (
            <p>Unavailable because distribution permission changed.</p>
          ) : (
            <>
              <p>
                {v.byte_size
                  ? `${Math.ceil(v.byte_size / 1024)} KiB`
                  : "ZIP not generated"}
                {v.expires_at
                  ? " · cache expires " +
                    new Date(v.expires_at).toLocaleString()
                  : ""}
              </p>
              <button
                className="project-button secondary"
                disabled={
                  !ack || busy || v.state === "building" || v.state === "queued"
                }
                onClick={() => prepare(v.version)}
              >
                Prepare or regenerate ZIP · 0 QC
              </button>
              {v.downloadable && (
                <a
                  aria-disabled={!ack}
                  className="project-button"
                  href={
                    ack
                      ? `/api/datasets/${d.id}/versions/${v.version}/download`
                      : undefined
                  }
                  onClick={(e) => {
                    if (!ack) e.preventDefault();
                  }}
                >
                  Download version {v.version} · 0 QC
                </a>
              )}
              <p className="project-id">
                ZIP SHA-256: {v.sha256 ?? "available after generation"}
              </p>
            </>
          )}
        </div>
      ))}
      <button className="project-link" onClick={() => router.refresh()}>
        Refresh availability
      </button>
      <p role="status">{message}</p>
    </section>
  );
}
