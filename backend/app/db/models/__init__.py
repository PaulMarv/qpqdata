"""Domain-organised SQLAlchemy models and their stable public import surface.

Importing this package registers all 25 tables on one Base.metadata for Alembic
and application queries. Domain modules reference foreign keys by table name;
they do not import one another or create database engines/connections.
"""

from .accounts import AuthSession, AuthThrottle, DevEmailVerification, User
from .base import Base, Record
from .credits import CreditLedgerEntry, ProjectReservation
from .datasets import (
    DatasetBuild,
    DatasetConsent,
    DatasetMember,
    DatasetPublication,
    DatasetReport,
    DatasetVersion,
)
from .moderation import ModerationDecision, NotificationOutbox, ProjectModerator
from .organisations import Organisation, OrganisationDomain, OrganisationMembership
from .projects import LabelDefinition, Project, ProjectCriterion, ProjectVersion
from .submissions import ImageAnnotation, RemovalRequest, Submission

__all__ = [
    "AuthSession",
    "AuthThrottle",
    "Base",
    "CreditLedgerEntry",
    "DatasetBuild",
    "DatasetConsent",
    "DatasetMember",
    "DatasetPublication",
    "DatasetReport",
    "DatasetVersion",
    "DevEmailVerification",
    "ImageAnnotation",
    "LabelDefinition",
    "ModerationDecision",
    "NotificationOutbox",
    "Organisation",
    "OrganisationDomain",
    "OrganisationMembership",
    "Project",
    "ProjectCriterion",
    "ProjectModerator",
    "ProjectReservation",
    "ProjectVersion",
    "Record",
    "RemovalRequest",
    "Submission",
    "User",
]
