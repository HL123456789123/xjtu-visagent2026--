"""One-time, local bootstrap for the first active super administrator."""

from dataclasses import dataclass

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.entity.db_models import OperationLog, Role, User, UserRole


class SuperAdminBootstrapError(ValueError):
    """Raised when the one-time bootstrap cannot proceed safely."""


@dataclass(frozen=True)
class SuperAdminBootstrapResult:
    user_id: int
    username: str
    created: bool


def find_active_super_admin(db: Session) -> User | None:
    return (
        db.query(User)
        .join(UserRole, UserRole.user_id == User.id)
        .join(Role, Role.id == UserRole.role_id)
        .filter(Role.name == "super_admin", User.is_active.is_(True))
        .first()
    )


def _validate_new_account(username: str, email: str | None, password: str | None) -> str:
    if not 3 <= len(username) <= 50:
        raise SuperAdminBootstrapError("Username must contain 3 to 50 characters.")
    if email is None:
        raise SuperAdminBootstrapError("Email is required when creating a new account.")
    try:
        normalized_email = str(TypeAdapter(EmailStr).validate_python(email.strip()))
    except ValidationError as exc:
        raise SuperAdminBootstrapError("Enter a valid email address.") from exc
    if password is None:
        raise SuperAdminBootstrapError("Password is required when creating a new account.")
    password_bytes = password.encode("utf-8")
    if len(password) < 12:
        raise SuperAdminBootstrapError("Password must contain at least 12 characters.")
    if len(password_bytes) > 72:
        raise SuperAdminBootstrapError("Password must not exceed 72 UTF-8 bytes.")
    if not any(char.isalpha() for char in password) or not any(char.isdigit() for char in password):
        raise SuperAdminBootstrapError("Password must contain both letters and numbers.")
    return normalized_email


def bootstrap_super_admin(
    db: Session,
    *,
    username: str,
    email: str | None = None,
    password: str | None = None,
) -> SuperAdminBootstrapResult:
    """Create or promote the first active super administrator.

    This operation deliberately refuses to run once an active super administrator
    exists. It is an offline deployment bootstrap, not a second role-management API.
    """

    username = username.strip()
    if find_active_super_admin(db) is not None:
        raise SuperAdminBootstrapError(
            "An active super administrator already exists; bootstrap is disabled."
        )

    super_admin_role = db.query(Role).filter(Role.name == "super_admin").first()
    if super_admin_role is None:
        raise SuperAdminBootstrapError(
            "The super_admin role is missing. Start the backend once before bootstrapping."
        )

    user = db.query(User).filter(User.username == username).first()
    created = user is None
    if user is None:
        normalized_email = _validate_new_account(username, email, password)
        if db.query(User).filter(User.email == normalized_email).first() is not None:
            raise SuperAdminBootstrapError("That email address is already registered.")
        user = User(
            username=username,
            email=normalized_email,
            hashed_password=hash_password(password or ""),
            is_active=True,
        )
        db.add(user)
        db.flush()
    elif not user.is_active:
        raise SuperAdminBootstrapError(
            "The selected account is disabled. Choose an active account or create a new one."
        )

    db.query(UserRole).filter(UserRole.user_id == user.id).delete(synchronize_session=False)
    db.add(UserRole(user_id=user.id, role_id=super_admin_role.id))
    db.add(
        OperationLog(
            user_id=None,
            username="system-bootstrap",
            module="auth",
            action="bootstrap_super_admin",
            target_type="user",
            target_id=str(user.id),
            description=(
                "Created the first active super administrator"
                if created
                else "Promoted an existing account as the first active super administrator"
            ),
            status="success",
        )
    )
    db.commit()
    db.refresh(user)
    return SuperAdminBootstrapResult(user_id=user.id, username=user.username, created=created)
