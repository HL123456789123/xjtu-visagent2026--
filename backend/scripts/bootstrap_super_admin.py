"""Interactive command for bootstrapping the first super administrator."""

from getpass import getpass
import sys

from app.database.session import SessionLocal
from app.entity.db_models import User
from app.services.super_admin_bootstrap import (
    SuperAdminBootstrapError,
    bootstrap_super_admin,
    find_active_super_admin,
)


def _confirm_existing_account(username: str) -> bool:
    print(f"The active account '{username}' already exists.")
    answer = input("Type PROMOTE to assign the super_admin role: ").strip()
    return answer == "PROMOTE"


def main() -> int:
    print("VisAgent first super administrator bootstrap")
    print("No password is stored in .env, command history, or application logs.")

    db = SessionLocal()
    try:
        if find_active_super_admin(db) is not None:
            print("Refused: an active super administrator already exists.", file=sys.stderr)
            return 2

        username = input("Username: ").strip()
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user is not None:
            if not _confirm_existing_account(username):
                print("Cancelled.")
                return 1
            email = None
            password = None
        else:
            email = input("Email: ").strip()
            password = getpass("Password (12+ characters, letters and numbers): ")
            password_confirmation = getpass("Confirm password: ")
            if password != password_confirmation:
                print("Passwords do not match.", file=sys.stderr)
                return 1
            confirmation = input("Type CREATE to create this super administrator: ").strip()
            if confirmation != "CREATE":
                print("Cancelled.")
                return 1

        result = bootstrap_super_admin(
            db,
            username=username,
            email=email,
            password=password,
        )
    except SuperAdminBootstrapError as exc:
        db.rollback()
        print(f"Bootstrap failed: {exc}", file=sys.stderr)
        return 2
    except Exception:
        db.rollback()
        print("Bootstrap failed because of an unexpected database error.", file=sys.stderr)
        return 3
    finally:
        db.close()

    action = "created" if result.created else "promoted"
    print(f"Success: account '{result.username}' was {action} as super_admin.")
    print("Sign in at http://127.0.0.1:3000 and change the password after first use.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
