# Empty pilot recovery activation — completed and verified

11 November 2026, 17:15 IST. The owner explicitly approved empty-database activation after
the initial automatic-review rejection. The checked operation committed and a fresh
database read verified READY plus the prepared epoch, with zero users and reports.
The hosted API independently reports database=ready and recovery=ready. Reviewer,
worker and cleanup prerequisites remain incomplete; overall /ready correctly returns 503.
No successful hosted login is claimed.

## Exact executed change

- Neon project airshedos, branch production, database neondb.
- Direct host ep-calm-resonance-b30pga6o.c-4.ap-southeast-1.aws.neon.tech.
- Offline management login neondb_owner, with verified TLS and trusted CA bundle.
- Change recovery_control/pilot from QUARANTINED with NULL epoch to READY with the
  fresh UUID already stored in the private API environment file; record release time.
- Use the existing RecoveryManager.initialise_empty operator implementation. It refuses
  an existing epoch or any existing identities, reports or media. Additional preflight
  verifies exact database/login, schema seva_0006 and current quarantine state.

This activates the database recovery boundary for authenticated application operations
using the matching epoch. It does not by itself make overall /ready pass: an approved
review unit, reviewer and live worker/cleanup heartbeats are still required. No users,
unit memberships, reports, provider calls, paid services or background processes are
created by this change. It must precede the first app login creating a verified identity.
Ingress/testing remains controlled; no real-data collection is authorised by this step.

## Approval and verification

An execution request was rejected by automatic approval review before the command ran:
schema initialisation and preview setup did not explicitly authorise this separate
release/security-state change. No alternate execution route was attempted. Explicit
owner approval of this exact activation was then obtained before executing it.

After approval, the guarded operation ran once. A fresh database read at
2026-11-11T11:45:46Z verified READY and the matching epoch, users=0 and reports=0.
GET https://airshedos-pilot-api.onrender.com/ready returned 503 with database=ready,
recovery=ready, worker/cleanup=stale_or_missing and triage=approved_unit_and_reviewer_required.
The private-image capability remains unavailable_text_only and optional providers unavailable.
No users, memberships, reports, paid services or processes were created. Do not rerun the
empty-install operation on this now-initialised target. Next: bind Vercel to this API,
verify a real Auth0 app login, and use its verified issuer/subject for approved provisioning.
