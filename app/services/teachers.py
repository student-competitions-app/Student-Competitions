"""Teachers: the teacher's invitable-role definition, and listing, editing, deactivating and
removing teachers.

See specs/008-teacher-management-consent/contracts/services.md §teachers and research D3, D9. A
teacher has three things, always written and deleted together (`TEACHER_INVITATION.grant` and
`.revoke`): the `teacher` role row, one `teacher_profiles` row, and one or more
`teacher_institutions` rows. A **current teacher** holds the role and has a profile row; anyone
else is `TeacherNotFound`. (The test cast's directly seeded teachers have no profile, so they are
not current teachers.)

These functions enforce no authorization: every route that calls them is
`@allow_roles(Role.ADMIN)`. Access levels and the competitions setting are only stored and shown
in this milestone (FR-013). Each change logs one line with ids and counts only.
"""

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import delete
from sqlmodel import Session, col, select

from app.core.config import AuthSettings
from app.core.db import utc_now
from app.models import AccessLevel, Role, TeacherInstitution, TeacherProfile, User, UserRole
from app.schemas.teachers import NOT_SELECTABLE, TeacherDetails
from app.services.consent import latest_consent_at, set_cutoff
from app.services.institutions import describe_institutions
from app.services.invitations import DetailLine
from app.services.users import end_all_sessions, get_roles

logger = logging.getLogger("uvicorn.error")


class _TeacherInvitation:
    """The teacher's `InvitableRole` (research D3). Its details are a `TeacherDetails`."""

    role = Role.TEACHER

    def details_to_payload(self, details: TeacherDetails) -> dict[str, Any]:
        return {
            "institutions": [
                [institution_id, details.institutions[institution_id].value]
                for institution_id in sorted(details.institutions)
            ],
            "can_create_competitions": details.can_create_competitions,
        }

    def details_from_payload(self, raw: Any) -> TeacherDetails:
        if not isinstance(raw, dict) or set(raw) != {"institutions", "can_create_competitions"}:
            raise ValueError("not teacher details")
        links, can_create = raw["institutions"], raw["can_create_competitions"]
        if not isinstance(links, list) or not links or not isinstance(can_create, bool):
            raise ValueError("not teacher details")
        institutions: dict[int, AccessLevel] = {}
        for link in links:
            if not isinstance(link, list) or len(link) != 2:
                raise ValueError("not a link")
            institution_id, level = link
            if not isinstance(institution_id, int) or isinstance(institution_id, bool):
                raise ValueError("not a link")
            if institution_id in institutions:
                raise ValueError("a link twice")
            institutions[institution_id] = AccessLevel(level)
        return TeacherDetails(institutions=institutions, can_create_competitions=can_create)

    def inviter_may_invite(self, session: Session, inviter: User, details: TeacherDetails) -> bool:
        """Any active administrator may invite a teacher to any institution."""
        assert inviter.id is not None
        return inviter.is_active and Role.ADMIN in get_roles(session, inviter.id)

    def details_acceptable(self, session: Session, details: TeacherDetails, lock: bool) -> bool:
        """Every institution exists and is selectable now (FR-009, FR-026)."""
        described = describe_institutions(session, details.institutions, lock=lock)
        return all(
            institution_id in described and described[institution_id].is_selectable
            for institution_id in details.institutions
        )

    def describe(self, session: Session, details: TeacherDetails) -> list[DetailLine]:
        """One line per institution, "Name (Region) — Read", sorted by label, by current names;
        then the competitions setting."""
        described = describe_institutions(session, details.institutions)
        lines = [
            DetailLine(f"{described[institution_id].label} — {level.label}")
            for institution_id, level in details.institutions.items()
            if institution_id in described
        ]
        lines.sort(key=lambda line: line.text.casefold())
        if details.can_create_competitions:
            lines.append(
                DetailLine(
                    "Can create competitions: Yes", "You will be able to create competitions."
                )
            )
        else:
            lines.append(
                DetailLine(
                    "Can create competitions: No", "You will not be able to create competitions."
                )
            )
        return lines

    def grant(self, session: Session, user: User, details: TeacherDetails, now: datetime) -> None:
        assert user.id is not None
        session.add(UserRole(user_id=user.id, role=Role.TEACHER, created_at=now))
        session.add(
            TeacherProfile(
                user_id=user.id,
                can_create_competitions=details.can_create_competitions,
                created_at=now,
                updated_at=now,
            )
        )
        for institution_id, level in details.institutions.items():
            session.add(
                TeacherInstitution(
                    user_id=user.id,
                    institution_id=institution_id,
                    access_level=level,
                    created_at=now,
                    updated_at=now,
                )
            )
        session.flush()

    def revoke(self, session: Session, user_id: int) -> None:
        session.execute(
            delete(TeacherInstitution).where(col(TeacherInstitution.user_id) == user_id)
        )
        session.execute(delete(TeacherProfile).where(col(TeacherProfile.user_id) == user_id))
        session.execute(
            delete(UserRole).where(
                col(UserRole.user_id) == user_id, col(UserRole.role) == Role.TEACHER
            )
        )


TEACHER_INVITATION = _TeacherInvitation()
"""Registered in `app.services.invitations.invitable_roles`."""


def grant_teacher(session: Session, user: User, details: TeacherDetails, now: datetime) -> None:
    """Give `user` the teacher role, profile and links. Does not commit."""
    TEACHER_INVITATION.grant(session, user, details, now)


class TeacherNotFound(LookupError):
    """No current teacher has this id: unknown, never a teacher, or removed."""

    def __init__(self, user_id: int) -> None:
        super().__init__(f"Teacher {user_id} not found")
        self.user_id = user_id


class InstitutionNotSelectable(ValueError):
    """An added institution is missing or not selectable (FR-009); nothing was changed."""

    def __init__(self) -> None:
        super().__init__(NOT_SELECTABLE)
        self.message = NOT_SELECTABLE


@dataclass(frozen=True)
class TeacherLink:
    institution_id: int
    label: str
    """"Name (Region)", by the current names."""
    access_level: AccessLevel
    is_selectable: bool
    """`False`: the institution or its region was deactivated after the link was made, so it is
    shown as deactivated and its level cannot change (FR-011)."""


@dataclass(frozen=True)
class TeacherView:
    user_id: int
    email: str
    first_name: str
    last_name: str
    links: list[TeacherLink]
    """Sorted by label, ignoring case."""
    can_create_competitions: bool
    consented_at: datetime | None
    """The latest teacher consent record."""
    is_active: bool
    """The teacher's own status: `False` while an administrator has deactivated them."""


def _current_teacher(session: Session, user_id: int, lock: bool = False) -> User:
    """The user, if they hold the teacher role and have a profile; `TeacherNotFound` otherwise,
    after rolling back, so a refused change keeps no row lock."""
    user = session.get(
        User, user_id, with_for_update=True if lock else None, populate_existing=lock
    )
    if (
        user is None
        or Role.TEACHER not in get_roles(session, user_id)
        or session.get(TeacherProfile, user_id) is None
    ):
        session.rollback()
        raise TeacherNotFound(user_id)
    return user


def _links(session: Session, user_id: int) -> dict[int, TeacherInstitution]:
    statement = select(TeacherInstitution).where(TeacherInstitution.user_id == user_id)
    return {row.institution_id: row for row in session.exec(statement)}


def _view(session: Session, user: User) -> TeacherView:
    assert user.id is not None
    stored = _links(session, user.id)
    described = describe_institutions(session, stored)
    links = [
        TeacherLink(
            institution_id=institution_id,
            label=described[institution_id].label,
            access_level=AccessLevel(row.access_level),
            is_selectable=described[institution_id].is_selectable,
        )
        for institution_id, row in stored.items()
        if institution_id in described
    ]
    links.sort(key=lambda link: (link.label.casefold(), link.institution_id))
    profile = session.get(TeacherProfile, user.id)
    assert profile is not None
    return TeacherView(
        user_id=user.id,
        email=user.email,
        first_name=user.first_name or "",
        last_name=user.last_name or "",
        links=links,
        can_create_competitions=profile.can_create_competitions,
        consented_at=latest_consent_at(session, user.id, Role.TEACHER),
        is_active=profile.is_active,
    )


def list_teachers(session: Session) -> list[TeacherView]:
    """Every current teacher, sorted by last name, then first name, ignoring case, ties by id
    (FR-038). Sorted in Python, as everywhere else."""
    statement = (
        select(User)
        .join(TeacherProfile, col(TeacherProfile.user_id) == col(User.id))
        .join(UserRole, col(UserRole.user_id) == col(User.id))
        .where(UserRole.role == Role.TEACHER)
    )
    views = [_view(session, user) for user in session.exec(statement)]
    return sorted(
        views,
        key=lambda view: (view.last_name.casefold(), view.first_name.casefold(), view.user_id),
    )


def get_teacher(session: Session, user_id: int) -> TeacherView:
    """The current teacher with this id, or `TeacherNotFound`."""
    return _view(session, _current_teacher(session, user_id))


def update_teacher(
    session: Session,
    user_id: int,
    first_name: str,
    last_name: str,
    institutions: Mapping[int, AccessLevel],
    can_create_competitions: bool,
    now: datetime | None = None,
) -> TeacherView:
    """Save an administrator's edit of a teacher, writing only what changed (FR-039–FR-041).

    The names and institutions are already validated by the router. The person's row is locked
    and checked to be a current teacher (`TeacherNotFound`). Newly added institutions are read
    `FOR SHARE` and must be selectable, or `InstitutionNotSelectable` is raised and nothing
    changes. A kept link that is no longer selectable keeps its stored level. Only added, removed
    and changed links are written, and only changed rows get a new `updated_at`. Sessions are never
    touched: editing does not sign the teacher out (FR-041).
    """
    now = now or utc_now()
    user = _current_teacher(session, user_id, lock=True)
    stored = _links(session, user_id)
    added = [institution_id for institution_id in institutions if institution_id not in stored]
    removed = [institution_id for institution_id in stored if institution_id not in institutions]
    described = describe_institutions(session, added, lock=True)
    if any(
        institution_id not in described or not described[institution_id].is_selectable
        for institution_id in added
    ):
        session.rollback()
        raise InstitutionNotSelectable()

    kept = describe_institutions(session, [i for i in stored if i in institutions])
    changed = 0
    for institution_id, row in stored.items():
        if institution_id in removed:
            session.delete(row)
            continue
        wanted = institutions[institution_id]
        selectable = institution_id in kept and kept[institution_id].is_selectable
        if selectable and row.access_level != wanted:
            row.access_level = wanted
            row.updated_at = now
            session.add(row)
            changed += 1
    for institution_id in added:
        session.add(
            TeacherInstitution(
                user_id=user_id,
                institution_id=institution_id,
                access_level=institutions[institution_id],
                created_at=now,
                updated_at=now,
            )
        )
    profile = session.get(TeacherProfile, user_id)
    assert profile is not None
    if profile.can_create_competitions != can_create_competitions:
        profile.can_create_competitions = can_create_competitions
        profile.updated_at = now
        session.add(profile)
    if (user.first_name, user.last_name) != (first_name, last_name):
        user.first_name = first_name
        user.last_name = last_name
        user.updated_at = now
        session.add(user)
    session.commit()
    logger.info(
        "Teacher updated: user_id=%s added=%s removed=%s changed=%s",
        user_id,
        len(added),
        len(removed),
        changed,
    )
    return get_teacher(session, user_id)


def set_teacher_active(
    session: Session, user_id: int, active: bool, now: datetime | None = None
) -> TeacherView:
    """Activate or deactivate the teacher; already in that status, nothing changes.

    Deactivating keeps the role, the links and the setting, but the teacher role stops being
    usable (`app.services.availability`), and the person is signed out everywhere in the same
    transaction, as on removal. They stay active as a user, so another role (administrator,
    student) still signs in.
    """
    now = now or utc_now()
    _current_teacher(session, user_id, lock=True)
    profile = session.get(TeacherProfile, user_id, populate_existing=True)
    assert profile is not None
    if profile.is_active == active:
        session.rollback()
        return get_teacher(session, user_id)
    profile.is_active = active
    profile.updated_at = now
    session.add(profile)
    if not active:
        end_all_sessions(session, user_id)
    session.commit()
    if active:
        logger.info("Teacher activated: user_id=%s", user_id)
    else:
        logger.info("Teacher deactivated: user_id=%s", user_id)
    return get_teacher(session, user_id)


def remove_teacher(
    session: Session, settings: AuthSettings, user_id: int, now: datetime | None = None
) -> None:
    """Take the teacher role, the links and the setting away (FR-042).

    The cut-off for the person's address is raised, so no invitation issued before now can be
    accepted (FR-027). The person is deactivated if no role is left, and signed out everywhere
    either way. The email, the names and the consent records stay until the person deletes their
    data.
    """
    now = now or utc_now()
    user = _current_teacher(session, user_id, lock=True)
    TEACHER_INVITATION.revoke(session, user_id)
    set_cutoff(session, settings.secret_key, user.email, Role.TEACHER, now)
    deactivated = not get_roles(session, user_id)
    if deactivated:
        user.is_active = False
    user.updated_at = now
    session.add(user)
    end_all_sessions(session, user_id)
    session.commit()
    logger.info("Teacher removed: user_id=%s deactivated=%s", user_id, deactivated)
