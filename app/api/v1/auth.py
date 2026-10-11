from fastapi import APIRouter, Request, Response, status

from app.core.config import get_settings
from app.core.deps import CurrentUser, DBSession, SessionServiceDep
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
)
from app.schemas.user import UserPublic
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])
_settings = get_settings()


@router.post(
    "/register",
    response_model=UserPublic,
    status_code=status.HTTP_201_CREATED,
)
async def register(payload: RegisterRequest, db: DBSession) -> UserPublic:
    user = await AuthService.register(
        db,
        email=payload.email,
        password=payload.password,
        first_name=payload.first_name,
        last_name=payload.last_name,
        school_name=payload.school_name,
        grade_id=payload.grade_id,
        country=payload.country,
        role=payload.role,
    )
    return UserPublic.model_validate(user)


@router.post("/login", response_model=UserPublic)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: DBSession,
    sessions: SessionServiceDep,
) -> UserPublic:
    user = await AuthService.authenticate(
        db, email=payload.email, password=payload.password
    )

    token = await sessions.create_session(
        db,
        user_id=user.id,
        ip=request.client.host if request.client else None,
        device_info=request.headers.get("user-agent"),
    )

    response.set_cookie(
        key=_settings.session_cookie_name,
        value=token,
        httponly=True,
        secure=_settings.session_cookie_secure,
        samesite=_settings.session_cookie_samesite,  # type: ignore[arg-type]
        max_age=_settings.session_ttl_seconds,
        path="/",
    )
    return UserPublic.model_validate(user)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    db: DBSession,
    sessions: SessionServiceDep,
) -> MessageResponse:
    token = request.cookies.get(_settings.session_cookie_name)
    if not token:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
    if token:
        await sessions.revoke(db, token)
    response.delete_cookie(_settings.session_cookie_name, path="/")
    return MessageResponse(message="Logged out")


@router.get("/me", response_model=UserPublic)
async def me(user: CurrentUser) -> UserPublic:
    return UserPublic.model_validate(user)


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    payload: ChangePasswordRequest,
    user: CurrentUser,
    db: DBSession,
    sessions: SessionServiceDep,
) -> MessageResponse:
    await AuthService.change_password(
        db, user, payload.current_password, payload.new_password
    )
    await sessions.revoke_all_for_user(db, user.id)
    return MessageResponse(message="Password updated. Please log in again.")