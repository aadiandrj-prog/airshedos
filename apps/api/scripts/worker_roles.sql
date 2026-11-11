-- Review and apply manually after seva_0006, with psql -v worker_role=... .
-- Creates no roles/passwords, provisions nothing, never invoked by the application.
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM :"worker_role";
GRANT USAGE ON SCHEMA public TO :"worker_role";
GRANT SELECT ON users, units, unit_memberships, reports, cases, media, jobs,
  processing_attempts, evidence_versions, evidence_fragments, review_events,
  maintenance_heartbeats, abuse_windows, alembic_version TO :"worker_role";
GRANT UPDATE ON jobs, processing_attempts TO :"worker_role";
GRANT INSERT ON processing_attempts, evidence_versions, evidence_fragments,
  review_events, processing_metrics TO :"worker_role";
GRANT SELECT ON processing_metrics TO :"worker_role";
GRANT SELECT, INSERT, UPDATE ON abuse_windows TO :"worker_role";
GRANT UPDATE (revision, evidence_sequence, latest_evidence_version_id) ON cases TO :"worker_role";
-- PostgreSQL row locks require UPDATE privilege. Only inert guard columns are
-- granted: the worker cannot reactivate a revoked member or suppressed report.
GRANT UPDATE (lock_guard) ON users, units, reports, unit_memberships TO :"worker_role";
-- No auth_sessions, auth_session_secrets, note, publication, invitation or media writes.
-- Dedicated cleanup role also needs DELETE processing_metrics (metrics expire at 30d).

-- Phase 6: worker pulse cannot forge retention cleanup health.
GRANT SELECT, INSERT, UPDATE ON worker_heartbeats TO :"worker_role";
GRANT SELECT ON recovery_control TO :"worker_role";
GRANT UPDATE (lock_guard) ON recovery_control TO :"worker_role";
