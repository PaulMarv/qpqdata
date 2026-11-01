from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import get_user, origin_check, transaction
from app.db.models import Project
from app.schemas.projects import (
    Category,
    ProjectDefinition,
    ProjectEdit,
    ProjectPage,
    ProjectView,
    State,
    Transition,
)
from app.services import projects
from app.services.auth import AuthError

router = APIRouter(prefix="/api/v1/projects", tags=["Collections"])


@router.post("", response_model=ProjectView, operation_id="createProject", status_code=201)
def create_project(body: ProjectDefinition, request: Request) -> ProjectView:
    with transaction(request) as session:
        origin_check(request)
        user = get_user(session, request, True)
        return projects.view(session, projects.create(session, user, body))


@router.get("", response_model=ProjectPage, operation_id="listProjects")
def list_projects(
    request: Request,
    q: str = Query(default="", max_length=200),
    category: Category | None = None,
    status: State | None = None,
    sort: str = Query(default="newest", pattern="^(newest|relevance)$"),
    page: int = Query(default=1, ge=1, le=100000),
    page_size: int = Query(default=10, ge=1, le=50),
) -> ProjectPage:
    # Public reads use the same explicit transaction/error-sanitisation boundary,
    # but do not require authentication to be enabled.
    with public_transaction(request) as session:
        return projects.discover(session, q, category, status, sort, page, page_size)


@router.get("/mine", response_model=ProjectPage, operation_id="listMyProjects")
def my_projects(
    request: Request,
    page: int = Query(default=1, ge=1, le=100000),
    page_size: int = Query(default=10, ge=1, le=50),
    status: State | None = None,
) -> ProjectPage:
    with transaction(request) as session:
        user = get_user(session, request)
        return projects.discover(session, "", None, status, "newest", page, page_size, owner=user)


@router.get("/{project_id}", response_model=ProjectView, operation_id="getProject")
def get_project(project_id: UUID, request: Request) -> ProjectView:
    with public_transaction(request) as session:
        project = session.get(Project, project_id)
        if not project:
            raise HTTPException(404, "Project not found.")
        if project.published_version is None or project.mode == "personal":
            if not request.app.state.settings.auth_enabled:
                raise HTTPException(404, "Project not found.")
            try:
                user = get_user(session, request)
                if user.id != project.owner_id:
                    raise HTTPException(404, "Project not found.")
            except (AuthError, AttributeError):
                raise HTTPException(404, "Project not found.") from None
        return projects.view(session, project)


@router.put("/{project_id}", response_model=ProjectView, operation_id="editProject")
def edit_project(project_id: UUID, body: ProjectEdit, request: Request) -> ProjectView:
    with transaction(request) as session:
        origin_check(request)
        user = get_user(session, request, True)
        return projects.view(
            session,
            projects.edit(session, user, project_id, body.expected_version, body.definition),
        )


@router.post("/{project_id}/status", response_model=ProjectView, operation_id="transitionProject")
def transition_project(project_id: UUID, body: Transition, request: Request) -> ProjectView:
    with transaction(request) as session:
        origin_check(request)
        user = get_user(session, request, True)
        return projects.view(
            session,
            projects.transition(session, user, project_id, body.status, body.expected_version),
        )


@contextmanager
def public_transaction(request: Request) -> Iterator[Session]:
    try:
        with Session(request.app.state.engine) as session, session.begin():
            yield session
    except AuthError as error:
        raise HTTPException(error.status, str(error)) from None
    except SQLAlchemyError:
        raise HTTPException(503, "Collection service unavailable. Try again later.") from None
