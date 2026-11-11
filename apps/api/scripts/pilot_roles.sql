-- Operator-reviewed least-privilege grants. Execute with psql identifier variables
-- api_role and session_role, after creating separate NOINHERIT LOGIN roles securely.
-- This script creates no roles/passwords and is NEVER run by application startup.
-- Database/schema ownership and migrations belong to a separate management role.
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM :"api_role", :"session_role";
GRANT USAGE ON SCHEMA public TO :"api_role", :"session_role";
GRANT SELECT ON users, units, unit_memberships, operator_grants, auth_sessions,
  reports, cases, media, processing_attempts, evidence_versions, evidence_fragments,
  evidence_redactions, review_events, internal_notes, reporter_updates,
  verification_tasks, jobs, idempotency_keys, privacy_requests, membership_proposals,
  abuse_windows, analysis_admissions, maintenance_heartbeats, alembic_version TO :"api_role";
GRANT SELECT, INSERT, UPDATE, DELETE ON reports, cases, media, processing_attempts,
  evidence_versions, evidence_fragments, evidence_redactions, review_events,
  internal_notes, reporter_updates, verification_tasks, jobs, idempotency_keys,
  privacy_requests, abuse_windows, analysis_admissions TO :"api_role";
GRANT SELECT, INSERT, DELETE ON access_audit, membership_proposals TO :"api_role";
REVOKE UPDATE ON review_events FROM :"api_role";
GRANT UPDATE (state) ON unit_memberships TO :"api_role";
GRANT SELECT, INSERT, DELETE ON information_requests, report_supplements TO :"api_role";
GRANT UPDATE (state) ON information_requests TO :"api_role";
GRANT UPDATE (lock_guard) ON users, units, auth_sessions TO :"api_role";
-- No API access to token ciphertext or user/operator/unit/role grant creation.
GRANT SELECT ON users, auth_sessions, auth_session_secrets TO :"session_role";
GRANT INSERT (id, issuer, subject, active, created_at) ON users TO :"session_role";
GRANT UPDATE (lock_guard) ON users TO :"session_role";
GRANT INSERT ON auth_sessions, auth_session_secrets TO :"session_role";
GRANT UPDATE (idle_expires_at, revoked_at) ON auth_sessions TO :"session_role";
GRANT UPDATE, DELETE ON auth_session_secrets TO :"session_role";
-- There are no shared-schema sequence grants: domain IDs are application UUIDv4.
-- Run maintenance with a separate restricted cleanup role, not API/BFF credentials.

-- Phase 6: release epoch is read/locked, never approved by API or session role.
GRANT SELECT ON recovery_control, worker_heartbeats TO :"api_role";
GRANT UPDATE (lock_guard) ON recovery_control TO :"api_role";
