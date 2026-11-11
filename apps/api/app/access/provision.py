"""Offline operator console. No HTTP grant/bootstrap endpoint or email-based linking.

Caller authenticates using a separately approved PostgreSQL management login. The
database role must match SEVA_OPERATOR_DATABASE_ROLE, never the API/BFF runtime role.
Targets must already exist under the configured verified OIDC issuer/subject.
"""

import argparse
import os
from datetime import timedelta
from uuid import UUID

from sqlalchemy import func, select, text

from app.persistence.contracts import AccessDenied, NotFound
from app.persistence.database import database
from app.persistence.models import (
    AccessAudit,
    AuthSession,
    AuthSessionSecret,
    Identity,
    Membership,
    MembershipProposal,
    OperatorGrant,
    Unit,
)
from app.persistence.repository import utcnow


class OperatorConsole:
    def __init__(self, sessions, *, database_role, issuer):
        if not database_role or not issuer.startswith("https://") or not issuer.endswith("/"):
            raise ValueError("Explicit operator role and verified issuer required")
        self.sessions, self.database_role, self.issuer = sessions, database_role, issuer

    def _connection(self, session):
        if session.scalar(text("SELECT session_user")) != self.database_role:
            raise AccessDenied("Approved offline management database login required")

    def _identity(self, session, subject):
        user = session.scalar(
            select(Identity)
            .where(
                Identity.issuer == self.issuer,
                Identity.subject == subject,
                Identity.active.is_(True),
            )
            .with_for_update()
        )
        if user is None:
            raise NotFound("Previously verified active identity required")
        return user

    @staticmethod
    def _audit(session, actor, target, unit, action):
        now = utcnow()
        session.add(
            AccessAudit(
                actor_id=actor,
                target_id=target,
                unit_id=unit,
                action=action,
                created_at=now,
                expires_at=now + timedelta(days=180),
            )
        )

    def bootstrap(self, subject, *, approved_initial_subject):
        if subject != approved_initial_subject or not approved_initial_subject:
            raise AccessDenied("Exact configured initial operator identity required")
        with self.sessions.begin() as session:
            self._connection(session)
            session.execute(text("SELECT pg_advisory_xact_lock(732008420021)"))
            if session.scalar(select(func.count()).select_from(OperatorGrant)):
                raise AccessDenied("Operator already bootstrapped; use controlled management")
            actor = self._identity(session, subject)
            session.add(OperatorGrant(user_id=actor.id, active=True, granted_at=utcnow()))
            self._audit(session, actor.id, actor.id, None, "OPERATOR_BOOTSTRAPPED")

    def execute(self, actor_subject, action, *, target_subject=None, name=None, proposal_id=None):
        with self.sessions.begin() as session:
            self._connection(session)
            actor = self._identity(session, actor_subject)
            grant = session.scalar(
                select(OperatorGrant)
                .where(OperatorGrant.user_id == actor.id, OperatorGrant.active.is_(True))
                .with_for_update()
            )
            if grant is None:
                raise AccessDenied("Active operator required")
            if action == "create-unit":
                if not name or not 1 <= len(name.strip()) <= 200 or len(name) > 200:
                    raise ValueError("Unit name must contain 1–200 characters")
                target = self._identity(session, target_subject)
                unit = Unit(name=name, approved_at=utcnow(), is_prototype=False)
                session.add(unit)
                session.flush()
                session.add(
                    Membership(
                        user_id=target.id,
                        unit_id=unit.id,
                        role="UNIT_ADMIN",
                        state="ACTIVE",
                        approved_by=actor.id,
                        approved_at=utcnow(),
                    )
                )
                self._audit(session, actor.id, target.id, unit.id, "UNIT_BOOTSTRAPPED")
                return unit.id
            if action == "approve":
                proposal = session.get(MembershipProposal, proposal_id, with_for_update=True)
                if (
                    proposal is None
                    or proposal.state != "PENDING"
                    or proposal.expires_at <= utcnow()
                ):
                    raise NotFound("Pending proposal not found")
                member = session.scalar(
                    select(Membership)
                    .where(
                        Membership.user_id == proposal.target_id,
                        Membership.unit_id == proposal.unit_id,
                    )
                    .with_for_update()
                )
                target = session.scalar(
                    select(Identity)
                    .where(Identity.id == proposal.target_id, Identity.active.is_(True))
                    .with_for_update()
                )
                if target is None:
                    raise NotFound("Active target identity required")
                if member is None:
                    session.add(
                        Membership(
                            user_id=target.id,
                            unit_id=proposal.unit_id,
                            role=proposal.role,
                            state="ACTIVE",
                            approved_by=actor.id,
                            approved_at=utcnow(),
                        )
                    )
                else:
                    member.state, member.role = "ACTIVE", proposal.role
                    member.approved_by, member.approved_at = actor.id, utcnow()
                proposal.state = "APPROVED"
                self._audit(session, actor.id, target.id, proposal.unit_id, "MEMBERSHIP_APPROVED")
                return proposal.id
            if action == "disable-account":
                target = self._identity(session, target_subject)
                target.active = False
                rows = list(
                    session.scalars(
                        select(AuthSession.id)
                        .where(AuthSession.user_id == target.id)
                        .with_for_update()
                    )
                )
                for row in session.scalars(select(AuthSession).where(AuthSession.id.in_(rows))):
                    row.revoked_at = utcnow()
                from sqlalchemy import delete

                session.execute(
                    delete(AuthSessionSecret).where(AuthSessionSecret.session_id.in_(rows))
                )
                for member in session.scalars(
                    select(Membership).where(Membership.user_id == target.id)
                ):
                    member.state = "REVOKED"
                self._audit(session, actor.id, target.id, None, "ACCOUNT_DISABLED")
                return target.id
            raise ValueError("Unknown operator action")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "action", choices=["bootstrap-operator", "create-unit", "approve", "disable-account"]
    )
    parser.add_argument("--actor-subject", required=True)
    parser.add_argument("--target-subject")
    parser.add_argument("--name")
    parser.add_argument("--proposal-id", type=UUID)
    args = parser.parse_args()
    engine, sessions = database(os.environ["SEVA_OPERATOR_DATABASE_URL"])
    try:
        console = OperatorConsole(
            sessions,
            database_role=os.environ["SEVA_OPERATOR_DATABASE_ROLE"],
            issuer=os.environ["AUTH0_ISSUER"],
        )
        if args.action == "bootstrap-operator":
            console.bootstrap(
                args.actor_subject,
                approved_initial_subject=os.environ["SEVA_INITIAL_OPERATOR_SUBJECT"],
            )
        else:
            console.execute(
                args.actor_subject,
                args.action,
                target_subject=args.target_subject,
                name=args.name,
                proposal_id=args.proposal_id,
            )
        print("Operator action committed")  # No identity/token/record contents.
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
