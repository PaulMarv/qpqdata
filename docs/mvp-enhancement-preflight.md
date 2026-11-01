# Final MVP enhancement prerequisite review — 1 November 2026

## Decision

**Phase 2E acceptance gate is not yet cleared. No enhancement implementation started.** Its implemented export/download paths pass the freshly executed automated tests, but the existing verification report explicitly leaves the deployed two-account publication/export/download exercise unexecuted. There is no newly established export code defect; this is an outstanding verification gap. An empty-library HTTP response does not prove a generated ZIP can be downloaded through the running Next.js transport.

The user expressly required stopping if the Phase 2E dependency is unfinished. This review therefore records the remaining acceptance work rather than changing collection modes, owner-contribution rules, capture components, database schemas or ledger semantics.

## Sources reviewed

- [Notion PRD](https://app.notion.com/p/408ad4cb30f881f983c8c8b472bd943c): includes the 1 November IMP-003/IMP-004 and rapid one-tap labelling decisions. These override the older no-self-contribution wording for future implementation, while retaining zero self-reward and existing historical ledger records.
- [Figma](https://www.figma.com/design/7M3EU9aXLzyJnpGjxtPdfI): inspected MVP 01–11 hierarchy/content, and retrieved rendered design context for MVP 11 developer handoff. Screen sequence: mode selection, personal setup, quick labels, camera, one-tap answer, capture success, private gallery, publication checks, owner additions, community capture and handoff rules. No screens were implemented from metadata alone.
- Current dataset routes, worker, export generator, private export adapter, download UI/Next.js transport, tests and [Phase 2E specification](phase-2e.md).
- Current submission eligibility, collection reservation/lifecycle and moderation reward services. Owners are currently rejected by the existing community contribution path; future owner images require a distinct zero-QC workflow, not removal of the self-payout guards.

## Checks executed in this review

| Check | Actual result |
| --- | --- |
| Full backend suite including real PostgreSQL | **124 passed**, five existing Starlette/httpx and Alembic deprecation warnings. Fresh disposable PostgreSQL database; application data was not used as test fixtures. |
| Dataset test coverage | ZIP contents, CSV/manifest, public metadata filtering, eligibility/licence gates, immutable versions, regeneration/missing-cache recovery, expiry, cross-user permissions, concurrent snapshots/workers, removal during generation/streaming, resource-limit branches and unchanged ledger history during downloads passed. |
| Frontend regression suite | **67 passed across 9 files**, including dataset download/consent and transport tests; Node 22 Docker test environment. |
| Running services | Database, backend, frontend, Mailpit, upload-cleaner, notifications and dataset worker healthy. Existing migration/development fixture containers report exit 0. No services or volumes reset. |
| Running database | `0008 (head)`; `alembic check` reports **No new upgrade operations detected**. No migration applied during this review. |
| Live API and frontend | Public dataset API returned HTTP 200 with `items: []`, `total: 0`; frontend health returned OK and `/datasets` returned HTTP 200. |
| New enhancement checks | Not applicable: no implementation, migration, build or lint changes. Prior quality/build results remain historical, not freshly rerun results. |

## Remaining Phase 2E acceptance work

Follow [the complete existing manual instructions](phase-2e.md#manual-end-to-end-verification), using synthetic non-identifying images and two accounts without resetting balances or volumes:

1. Submit and approve a community image; confirm approval alone does not publish it. Record wallet/ledger state after the ordinary contribution payout.
2. Exercise explicit owner publication policy, contributor distribution opt-in and separate owner image authorisation through the running frontend.
3. Create a version, let the real Compose dataset worker generate it, and download the free ZIP through the frontend as a guest. Inspect archive contents, labels, manifest, licence, hashes and privacy exclusions. Confirm download/preparation caused no credit changes.
4. Add an eligible second image and create version 2; verify version 1 remains unchanged. Exercise consent withdrawal/removal and confirm all affected versions become unavailable through the frontend. Publish a replacement version excluding the restricted image.
5. Verify cache expiry/regeneration and interrupted/retried generation/download on the deployed stack. Automated tests already cover these branches; deployed end-to-end results are still outstanding.

Manual mobile appearance and actual camera/device acceptance remain separate outstanding checks. The pre-crash original-image checksum baseline was lost from `/tmp` during the prior Docker incident; that historical comparison cannot be recreated retrospectively. Existing data/image volumes were retained, and this review made no image changes.

## Deferred enhancement scope

Once the dependency is accepted, implement Personal/Crowdsourced mode independently of Private/Public visibility; private-by-default zero-QC personal collection capture/gallery/label editing/export; zero-QC owner images with target/provenance and transactional reservation protection; and the shared capture → one essential label → Save & Capture Next flow. Preserve rights/privacy validation and per-image provenance. Do not implement cohorts, expanded notifications, offline synchronisation or Phase 3.


## Gate resolution after instruction to proceed — 1 November 2026

Completed the missing two-account live HTTP path before modifying application code: Mailpit-bound authentication, approval, explicit publication/consent/authorisation, real worker ZIP generation, guest frontend download, correct archive/manifest/image hashes, versions 1–3, old-version identity, withdrawal revocation, retained private source and unchanged wallets during dataset actions. The final enhancement subsequently regenerated the pre-enhancement archive with an identical SHA-256. Physical browser/mobile acceptance remains distinct from these successful HTTP checks. See [final implementation](final-mvp-enhancement.md) and [verification](verification.md).
