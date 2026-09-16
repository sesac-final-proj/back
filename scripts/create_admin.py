import argparse
import getpass

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.user import User, UserRole


def main() -> None:
    parser = argparse.ArgumentParser(description="관리자 계정을 생성합니다.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--nickname", default="관리자")
    args = parser.parse_args()

    password = getpass.getpass("Password: ")
    password_confirm = getpass.getpass("Password again: ")
    if password != password_confirm:
        raise SystemExit("비밀번호가 일치하지 않습니다.")
    if len(password) < 8:
        raise SystemExit("비밀번호는 8자 이상이어야 합니다.")

    db = SessionLocal()
    try:
        exists = db.scalar(select(User.id).where(User.email == args.email))
        if exists is not None:
            raise SystemExit("이미 존재하는 이메일입니다.")

        db.add(
            User(
                email=args.email,
                password_hash=hash_password(password),
                nickname=args.nickname,
                role=UserRole.ADMIN,
            )
        )
        db.commit()
        print("관리자 계정이 생성되었습니다.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
