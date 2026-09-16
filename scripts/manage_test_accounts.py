"""테스트 계정 후보 조회 및 연관 데이터 삭제 도구."""

from __future__ import annotations

import argparse

from sqlalchemy import inspect, text

from app.core.db import engine


def candidates() -> list[dict]:
    statement = text("""
        SELECT u.id, u.email, u.nickname, u.role, u.created_at,
               string_agg(sa.provider, ',') AS providers
        FROM users AS u
        LEFT JOIN social_accounts AS sa ON sa.user_id = u.id
        WHERE lower(u.email) LIKE '%test%'
           OR lower(u.nickname) LIKE '%test%'
           OR lower(u.nickname) LIKE '%테스트%'
        GROUP BY u.id
        ORDER BY u.created_at DESC
    """)
    with engine.connect() as connection:
        return [dict(row._mapping) for row in connection.execute(statement)]


def delete_user(user_id: int) -> None:
    """users.id를 참조하는 행을 먼저 삭제한 뒤 사용자 행을 삭제한다."""
    inspector = inspect(engine)
    references: list[tuple[str, str]] = []
    for table in inspector.get_table_names(schema="public"):
        for foreign_key in inspector.get_foreign_keys(table, schema="public"):
            if foreign_key.get("referred_table") != "users":
                continue
            columns = foreign_key.get("constrained_columns") or []
            if len(columns) == 1:
                references.append((table, columns[0]))

    with engine.begin() as connection:
        exists = connection.execute(
            text("SELECT id FROM users WHERE id = :user_id FOR UPDATE"),
            {"user_id": user_id},
        ).scalar_one_or_none()
        if exists is None:
            raise SystemExit(f"user {user_id} does not exist")
        for table, column in references:
            connection.execute(
                text(f'DELETE FROM "{table}" WHERE "{column}" = :user_id'),
                {"user_id": user_id},
            )
        connection.execute(text("DELETE FROM users WHERE id = :user_id"), {"user_id": user_id})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delete-user-id", type=int)
    args = parser.parse_args()
    if args.delete_user_id is not None:
        delete_user(args.delete_user_id)
        print(f"deleted user_id={args.delete_user_id}")
        return
    for row in candidates():
        print(
            f"id={row['id']} email={row['email']} nickname={row['nickname']} "
            f"role={row['role']} providers={row['providers']} created_at={row['created_at']}"
        )


if __name__ == "__main__":
    main()
