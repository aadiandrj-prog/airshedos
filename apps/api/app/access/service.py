import hashlib
import re
from dataclasses import replace
from datetime import timedelta

from sqlalchemy import func, select

from app.access.contracts import (
    AuthorityList,
    AuthoritySummary,
    MemberRead,
    MeRead,
    PilotCasePacket,
    ProposalRead,
    ResidentList,
    ResidentSummary,
    UnitRead,
)
from app.access.limits import reserve_paid_analysis
from app.access.tokens import InvalidIdentity
from app.persistence.contracts import AccessDenied, NotFound, Principal
from app.persistence.models import (
    AccessAudit,
    AuthSession,
    Case,
    EvidenceVersion,
    Identity,
    Membership,
    MembershipProposal,
    OperatorGrant,
    Report,
    Unit,
)


class AccessService:
    def __init__(self, repository, verifier, media=None):
        self.repo, self.verifier, self.media = repository, verifier, media
        self.repo.require_session = True  # All public v2 operations use the strict repository.

    def authenticate(self, authorization, binding):
        if (
            not isinstance(authorization, str)
            or not authorization.startswith("Bearer ")
            or not isinstance(binding, str)
            or not re.fullmatch(r"[0-9a-f]{64}", binding)
        ):
            raise InvalidIdentity("Sign in required")
        claims = self.verifier.verify(authorization[7:])
        with self.repo.sessions.begin() as session:
            row = session.scalar(
                select(AuthSession).where(
                    AuthSession.binding_hash == hashlib.sha256(binding.encode()).hexdigest(),
                    AuthSession.issuer == claims["iss"],
                    AuthSession.subject == claims["sub"],
                    AuthSession.revoked_at.is_(None),
                    AuthSession.idle_expires_at > self.repo.clock(),
                    AuthSession.absolute_expires_at > self.repo.clock(),
                )
            )
            if row is None:
                raise InvalidIdentity("Sign in required")
            principal = Principal(claims["iss"], claims["sub"], session_id=row.id)
            try:
                self.repo.identity(session, principal)
            except AccessDenied as exc:
                raise InvalidIdentity("Sign in required") from exc
            return principal

    def _unit(self, session, principal, unit_id, *, admin=False, lock=False):
        user = self.repo.identity(session, principal, lock=lock)
        query = (
            select(Membership)
            .join(Unit)
            .where(
                Membership.user_id == user.id,
                Membership.unit_id == unit_id,
                Membership.state == "ACTIVE",
                Membership.approved_by.is_not(None),
                Membership.approved_at.is_not(None),
                Unit.approved_at.is_not(None),
                Unit.is_prototype.is_(False),
            )
        )
        if admin:
            query = query.where(Membership.role == "UNIT_ADMIN")
        if lock:
            query = query.with_for_update(of=[Membership, Unit], read=True)
        membership = session.scalar(query)
        if membership is None:
            raise NotFound("Unit not found")
        return user, membership

    def me(self, principal):
        with self.repo.sessions.begin() as session:
            user = self.repo.identity(session, principal)
            units = session.execute(
                select(Unit, Membership.role)
                .join(Membership)
                .where(
                    Membership.user_id == user.id,
                    Membership.state == "ACTIVE",
                    Membership.approved_at.is_not(None),
                    Membership.approved_by.is_not(None),
                    Unit.approved_at.is_not(None),
                    Unit.is_prototype.is_(False),
                )
                .order_by(Unit.id)
            ).all()
            return MeRead(
                id=user.id, units=[UnitRead(id=u.id, name=u.name, role=r) for u, r in units]
            )

    def reports(self, principal, *, limit=20, offset=0):
        self._page(limit, offset)
        with self.repo.sessions.begin() as session:
            user = self.repo.identity(session, principal)
            scoped = select(Report).where(
                Report.reporter_user_id == user.id,
                Report.deletion_state == "ACTIVE",
                Report.content_expires_at > self.repo.clock(),
            )
            total = session.scalar(select(func.count()).select_from(scoped.subquery()))
            rows = session.scalars(
                scoped.order_by(Report.accepted_at.desc(), Report.id).limit(limit).offset(offset)
            )
            return ResidentList(
                total=total,
                items=[
                    ResidentSummary(
                        content_expires_at=r.content_expires_at,
                        id=r.id,
                        receipt_id=r.receipt_id,
                        accepted_at=r.accepted_at,
                        processing=self.repo.processing_projection(
                            session, r, session.scalar(select(Case).where(Case.report_id == r.id))
                        ).state,
                    )
                    for r in rows
                ],
            )

    @staticmethod
    def _page(limit, offset):
        if not 1 <= limit <= 50 or not 0 <= offset <= 1000:
            raise ValueError("Invalid page")

    def _cases(self, session, principal, unit_id, state=None, query=None, assignment=None):
        user, _ = self._unit(session, principal, unit_id)
        scoped = (
            select(Case)
            .join(Report)
            .where(
                Case.assigned_unit_id == unit_id,
                Report.deletion_state == "ACTIVE",
                Report.content_expires_at > self.repo.clock(),
            )
        )
        if state:
            scoped = scoped.where(Case.review_state == state)
        if assignment == "mine":
            scoped = scoped.where(Case.assigned_reviewer_id == user.id)
        elif assignment == "unassigned":
            scoped = scoped.where(Case.assigned_reviewer_id.is_(None))
        if query:
            # Literal substring search, not a wildcard injection or a global search then filter.
            scoped = scoped.where(Report.description.contains(query, autoescape=True))
        return scoped

    def cases(
        self, principal, unit_id, *, limit=20, offset=0, state=None, query=None, assignment=None
    ):
        self._page(limit, offset)
        with self.repo.sessions.begin() as session:
            scoped = self._cases(session, principal, unit_id, state, query, assignment)
            rows = session.scalars(
                scoped.order_by(Case.created_at.desc(), Case.id).limit(limit).offset(offset)
            )
            counts = dict(
                session.execute(
                    select(Case.review_state, func.count())
                    .where(Case.id.in_(scoped.with_only_columns(Case.id)))
                    .group_by(Case.review_state)
                ).all()
            )
            return AuthorityList(
                total=sum(counts.values()),
                state_counts=counts,
                items=[
                    AuthoritySummary(
                        content_expires_at=session.get(Report, c.report_id).content_expires_at,
                        id=c.id,
                        created_at=c.created_at,
                        review_state=c.review_state,
                        revision=c.revision,
                        reported_place=session.get(Report, c.report_id).reported_place,
                        declared_category=session.get(Report, c.report_id).declared_category,
                        latitude=session.get(Report, c.report_id).reported_latitude,
                        longitude=session.get(Report, c.report_id).reported_longitude,
                        assigned_member_id=session.scalar(
                            select(Membership.id).where(
                                Membership.unit_id == unit_id,
                                Membership.user_id == c.assigned_reviewer_id,
                            )
                        )
                        if c.assigned_reviewer_id
                        else None,
                    )
                    for c in rows
                ],
            )

    def map_points(self, principal, unit_id):
        with self.repo.sessions.begin() as session:
            scoped = self._cases(session, principal, unit_id)
            rows = session.execute(
                select(
                    Case.id,
                    Report.reported_latitude,
                    Report.reported_longitude,
                    Report.content_expires_at,
                )
                .join(Report)
                .where(Case.id.in_(scoped.with_only_columns(Case.id)))
                .order_by(Case.id)
                .limit(50)
            )
            return [
                {
                    "case_id": str(i),
                    "latitude": lat,
                    "longitude": lng,
                    "content_expires_at": expires,
                }
                for i, lat, lng, expires in rows
            ]

    def packet(self, principal, unit_id, case_id):
        principal = replace(principal, unit_id=unit_id)
        with self.repo.sessions.begin() as session:
            _, case, _ = self.repo._case(session, principal, case_id)
            versions = session.scalars(
                select(EvidenceVersion)
                .where(EvidenceVersion.case_id == case.id)
                .order_by(EvidenceVersion.version)
            )
            # Payload export is unapproved: explicit metadata-only versioned pilot packet.
            return PilotCasePacket(
                case_id=case.id,
                created_at=case.created_at,
                review_state=case.review_state,
                revision=case.revision,
                evidence_versions=[
                    {
                        "id": str(v.id),
                        "version": v.version,
                        "input_policy": v.input_policy,
                        "content": "OMITTED_BY_EXPORT_POLICY",
                    }
                    for v in versions
                ],
            )

    def roster(self, principal, unit_id):
        with self.repo.sessions.begin() as session:
            self._unit(session, principal, unit_id, admin=True)
            return [
                MemberRead(id=m.id, role=m.role, state=m.state)
                for m in session.scalars(
                    select(Membership).where(Membership.unit_id == unit_id).order_by(Membership.id)
                )
            ]

    def propose(self, principal, unit_id, target_subject):
        with self.repo.sessions.begin() as session:
            user, _ = self._unit(session, principal, unit_id, admin=True, lock=True)
            target = session.scalar(
                select(Identity).where(
                    Identity.issuer == principal.issuer,
                    Identity.subject == target_subject,
                    Identity.active.is_(True),
                )
            )
            if target is None:
                raise NotFound("Eligible identity not found")
            proposal = MembershipProposal(
                unit_id=unit_id,
                target_id=target.id,
                proposed_by=user.id,
                role="REVIEWER",
                created_at=self.repo.clock(),
                expires_at=self.repo.clock() + timedelta(days=7),
            )
            session.add(proposal)
            self._audit(session, user.id, target.id, unit_id, "MEMBERSHIP_PROPOSED")
            session.flush()
            return ProposalRead(id=proposal.id, state=proposal.state)

    def suspend(self, principal, unit_id, membership_id):
        with self.repo.sessions.begin() as session:
            user, _ = self._unit(session, principal, unit_id, admin=True, lock=True)
            member = session.scalar(
                select(Membership)
                .where(
                    Membership.id == membership_id,
                    Membership.unit_id == unit_id,
                    Membership.role == "REVIEWER",
                    Membership.user_id != user.id,
                )
                .with_for_update()
            )
            if member is None:
                raise NotFound("Membership not found")
            member.state = "SUSPENDED"
            self._audit(session, user.id, member.user_id, unit_id, "MEMBERSHIP_SUSPENDED")

    def _operator(self, session, principal):
        user = self.repo.identity(session, principal, lock=True)
        if (
            session.scalar(
                select(OperatorGrant)
                .where(OperatorGrant.user_id == user.id, OperatorGrant.active.is_(True))
                .with_for_update(read=True)
            )
            is None
        ):
            raise AccessDenied("Operator required")
        return user

    def approve(self, principal, proposal_id):
        with self.repo.sessions.begin() as session:
            actor = self._operator(session, principal)
            proposal = session.get(MembershipProposal, proposal_id, with_for_update=True)
            if (
                proposal is None
                or proposal.state != "PENDING"
                or proposal.expires_at <= self.repo.clock()
            ):
                raise NotFound("Pending proposal not found")
            target = session.scalar(
                select(Identity)
                .where(Identity.id == proposal.target_id, Identity.active.is_(True))
                .with_for_update(read=True)
            )
            if target is None:
                raise NotFound("Eligible identity not found")
            member = session.scalar(
                select(Membership)
                .where(Membership.user_id == target.id, Membership.unit_id == proposal.unit_id)
                .with_for_update()
            )
            if member is None:
                member = Membership(
                    user_id=target.id,
                    unit_id=proposal.unit_id,
                    role=proposal.role,
                    state="ACTIVE",
                    approved_by=actor.id,
                    approved_at=self.repo.clock(),
                )
                session.add(member)
            else:
                # Operator alone can reactivate/escalate; proposal is not a grant.
                member.state, member.role = "ACTIVE", proposal.role
                member.approved_by, member.approved_at = actor.id, self.repo.clock()
            proposal.state = "APPROVED"
            self._audit(session, actor.id, target.id, proposal.unit_id, "MEMBERSHIP_APPROVED")

    def reserve_analysis(self, principal, unit_id, case_id):
        principal = replace(principal, unit_id=unit_id)
        with self.repo.sessions.begin() as session:
            self.repo._case(session, principal, case_id, lock=True)
            return reserve_paid_analysis(session, case_id, self.repo.limits)

    def _audit(self, session, actor_id, target_id, unit_id, action):
        session.add(
            AccessAudit(
                actor_id=actor_id,
                target_id=target_id,
                unit_id=unit_id,
                action=action,
                created_at=self.repo.clock(),
                expires_at=self.repo.clock() + timedelta(days=180),
            )
        )
