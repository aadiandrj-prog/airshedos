-- Apply manually after seva_0006 with psql -v cleanup_role=... .
-- The role must be a dedicated non-owner LOGIN with NOINHERIT, no role memberships,
-- no SUPERUSER/CREATEROLE/CREATEDB/REPLICATION/BYPASSRLS. Never use Neon owner credentials
-- in the running cleanup service. This script creates no roles or passwords.
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM :"cleanup_role";
GRANT USAGE ON SCHEMA public TO :"cleanup_role";
GRANT SELECT ON reports, cases, media, processing_attempts, evidence_versions,
  evidence_fragments, evidence_redactions, review_events, internal_notes,
  reporter_updates, verification_tasks, jobs, idempotency_keys, privacy_requests,
  information_requests, report_supplements, maintenance_heartbeats, analysis_admissions,
  processing_metrics, abuse_windows, access_audit, membership_proposals TO :"cleanup_role";
GRANT SELECT (id, revoked_at, idle_expires_at, absolute_expires_at) ON auth_sessions
  TO :"cleanup_role";
GRANT SELECT (session_id) ON auth_session_secrets TO :"cleanup_role";
GRANT DELETE ON reports, cases, media, processing_attempts, evidence_versions,
  evidence_fragments, evidence_redactions, review_events, internal_notes,
  reporter_updates, verification_tasks, jobs, idempotency_keys, privacy_requests,
  information_requests, report_supplements, analysis_admissions, processing_metrics,
  abuse_windows, access_audit, membership_proposals, auth_sessions, auth_session_secrets
  TO :"cleanup_role";
GRANT INSERT ON privacy_requests, evidence_redactions, maintenance_heartbeats
  TO :"cleanup_role";
GRANT UPDATE (description, declared_category, reported_place, reported_latitude,
  reported_longitude, declared_capture_at, capture_time_basis, deletion_state,
  purged_at, audit_expires_at) ON reports TO :"cleanup_role";
GRANT UPDATE (external_reference, latest_evidence_version_id) ON cases TO :"cleanup_role";
GRANT UPDATE (object_key, sha256, size_bytes, state) ON media TO :"cleanup_role";
GRANT UPDATE (reason) ON review_events TO :"cleanup_role";
GRANT UPDATE (body) ON internal_notes, report_supplements TO :"cleanup_role";
GRANT UPDATE (message) ON reporter_updates TO :"cleanup_role";
GRANT UPDATE (instructions, outcome, state) ON verification_tasks TO :"cleanup_role";
GRANT UPDATE (prompt, state) ON information_requests TO :"cleanup_role";
GRANT UPDATE (fingerprint, tombstone, consumed_until) ON idempotency_keys TO :"cleanup_role";
GRANT UPDATE (state, lease_token, lease_expires_at) ON jobs TO :"cleanup_role";
GRANT UPDATE (state, ended_at) ON processing_attempts TO :"cleanup_role";
GRANT UPDATE (input_fingerprint) ON evidence_versions TO :"cleanup_role";
GRANT UPDATE (payload, content_sha256, state) ON evidence_fragments TO :"cleanup_role";
GRANT UPDATE (purged_at) ON privacy_requests TO :"cleanup_role";
GRANT UPDATE (succeeded_at) ON maintenance_heartbeats TO :"cleanup_role";
-- No token ciphertext reads, new domain records, membership/operator grants, worker
-- heartbeat writes or recovery release/epoch changes. Deletion is intentionally
-- privileged; the reviewed maintenance service supplies retention predicates.
