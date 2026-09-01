import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.v1.nicknames.resources import load_forbidden_words
from app.api.v1.nicknames.validator import NicknameValidator
from app.core.config import settings
from app.core.db import Base, get_db
from app.core.security import create_access_token, decode_token, hash_password
from app.main import app
from app.models.user import SocialAccount, User, UserRole


class AuthNicknameApiTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.engine = create_engine(
            f"sqlite:///{self.db_path}",
            connect_args={"check_same_thread": False},
        )
        self.SessionLocal = sessionmaker(bind=self.engine, autocommit=False, autoflush=False)
        Base.metadata.create_all(bind=self.engine)

        def override_get_db():
            db = self.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db

        self.forbidden_path = Path(self.temp_dir.name) / "forbidden_words.json"
        self.forbidden_path.write_text(
            json.dumps({"forbidden_words": ["금칙어"]}, ensure_ascii=False),
            encoding="utf-8",
        )
        settings.FORBIDDEN_WORDS_PATH = str(self.forbidden_path)
        settings.APP_ENV = "test"
        load_forbidden_words.cache_clear()
        self.client = TestClient(app)

    def tearDown(self):
        app.dependency_overrides.clear()
        load_forbidden_words.cache_clear()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def _create_user(self, email="user@example.com", password="password1234", role=UserRole.USER):
        db = self.SessionLocal()
        user = User(
            email=email,
            password_hash=hash_password(password),
            nickname=f"닉네임{len(email)}",
            role=role,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        db.close()
        return user

    def test_signup_login_refresh_logout_flow(self):
        signup = self.client.post(
            "/api/v1/auth/signup",
            json={"email": "new@example.com", "password": "password1234", "nickname": "가입자1"},
        )
        self.assertEqual(signup.status_code, 200)

        login = self.client.post(
            "/api/v1/auth/login",
            json={"email": "new@example.com", "password": "password1234"},
        )
        self.assertEqual(login.status_code, 200)
        tokens = login.json()

        access_payload = decode_token(tokens["access_token"])
        refresh_payload = decode_token(tokens["refresh_token"])
        self.assertEqual(access_payload["role"], "user")
        self.assertEqual(refresh_payload["role"], "user")
        self.assertEqual(access_payload["type"], "access")
        self.assertEqual(refresh_payload["type"], "refresh")

        refreshed = self.client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        self.assertEqual(refreshed.status_code, 200)

        reused = self.client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        self.assertEqual(reused.status_code, 401)

    def test_admin_token_and_admin_only_api(self):
        user = self._create_user(email="normal@example.com", role=UserRole.USER)
        admin = self._create_user(email="admin@example.com", role=UserRole.ADMIN)

        user_token = create_access_token(str(user.id), role="user", provider="local")
        blocked = self.client.get("/api/v1/auth/admin/me", headers={"Authorization": f"Bearer {user_token}"})
        self.assertEqual(blocked.status_code, 403)

        login = self.client.post(
            "/api/v1/auth/admin/login",
            json={"email": "admin@example.com", "password": "password1234"},
        )
        self.assertEqual(login.status_code, 200)
        payload = decode_token(login.json()["access_token"])
        self.assertEqual(payload["role"], "admin")

        allowed = self.client.get(
            "/api/v1/auth/admin/me",
            headers={"Authorization": f"Bearer {login.json()['access_token']}"},
        )
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.json()["id"], admin.id)

    def test_nickname_recommendation_availability_and_selection(self):
        user = self._create_user(email="nickname@example.com")
        token = create_access_token(str(user.id), role="user", provider="local")

        recommendation = self.client.get("/api/v1/nicknames/recommendation")
        self.assertEqual(recommendation.status_code, 200)
        self.assertIn("nickname", recommendation.json())

        available = self.client.get("/api/v1/nicknames/availability", params={"nickname": "수달1"})
        self.assertEqual(available.status_code, 200)
        self.assertTrue(available.json()["available"])

        invalid = self.client.get("/api/v1/nicknames/availability", params={"nickname": "Happy수달"})
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(invalid.json()["message"], "한글과 숫자만 입력해주세요.")

        forbidden = self.client.get("/api/v1/nicknames/availability", params={"nickname": "금칙어1"})
        self.assertEqual(forbidden.status_code, 400)
        self.assertEqual(forbidden.json()["message"], "사용할 수 없는 표현이 포함되어 있어요.")

        selected = self.client.post(
            "/api/v1/nicknames/selection",
            headers={"Authorization": f"Bearer {token}"},
            json={"nickname": "수달1"},
        )
        self.assertEqual(selected.status_code, 200)
        self.assertEqual(selected.json()["nickname"], "수달1")

        duplicate = self.client.get("/api/v1/nicknames/availability", params={"nickname": "수달1"})
        self.assertEqual(duplicate.status_code, 409)
        self.assertFalse(duplicate.json()["available"])

    def test_nickname_validator_policy(self):
        validator = NicknameValidator(forbidden_words=["금칙어"])
        for nickname in ["수", "수달1", "나는공주1", "토끼777"]:
            with self.subTest(nickname=nickname):
                self.assertEqual(validator.validate(nickname), nickname)

        cases = {
            "": "NICKNAME_REQUIRED",
            "12345": "NICKNAME_REQUIRES_KOREAN",
            "Happy수달": "NICKNAME_INVALID_CHARACTERS",
            "수달!": "NICKNAME_INVALID_CHARACTERS",
            "포근한 수달": "NICKNAME_CONTAINS_SPACE",
            "너무긴닉네임12": "NICKNAME_TOO_LONG",
            "금칙어1": "NICKNAME_FORBIDDEN",
        }
        for nickname, code in cases.items():
            with self.subTest(nickname=nickname):
                with self.assertRaises(Exception) as context:
                    validator.validate(nickname)
                self.assertEqual(context.exception.code, code)

    def test_forbidden_words_path_errors(self):
        settings.FORBIDDEN_WORDS_PATH = str(Path(self.temp_dir.name) / "missing.json")
        load_forbidden_words.cache_clear()
        with self.assertRaises(FileNotFoundError):
            load_forbidden_words()

        bad_path = Path(self.temp_dir.name) / "bad.json"
        bad_path.write_text("{", encoding="utf-8")
        settings.FORBIDDEN_WORDS_PATH = str(bad_path)
        load_forbidden_words.cache_clear()
        with self.assertRaises(json.JSONDecodeError):
            load_forbidden_words()

        settings.APP_ENV = "prod"
        settings.FORBIDDEN_WORDS_PATH = ""
        load_forbidden_words.cache_clear()
        with self.assertRaises(RuntimeError):
            load_forbidden_words()

    def test_decode_rejects_tampered_token(self):
        token = create_access_token("1")
        with self.assertRaises(jwt.PyJWTError):
            decode_token(token + "tampered")

    def test_env_backed_settings_and_legacy_oauth_routes(self):
        self.assertTrue(hasattr(settings, "KAKAO_REST_API_KEY"))
        self.assertTrue(hasattr(settings, "KAKAO_ADMIN_KEY"))
        self.assertTrue(hasattr(settings, "REDIS_HOST"))
        self.assertTrue(hasattr(settings, "REDIS_PW"))
        self.assertTrue(hasattr(settings, "NAVER_MAPS_API_KEY_ID"))
        self.assertTrue(hasattr(settings, "NAVER_MAPS_API_KEY_SECRET"))

        kakao = self.client.get("/auth/login/kakao")
        self.assertEqual(kakao.status_code, 200)
        self.assertIn("auth_url", kakao.json())

        naver = self.client.get("/auth/login/naver")
        self.assertEqual(naver.status_code, 200)
        self.assertIn("auth_url", naver.json())

    def test_oauth_redirect_uri_uses_provider_settings(self):
        original_kakao_redirect_uri = settings.KAKAO_REDIRECT_URI
        original_oauth_redirect_uri = settings.OAUTH_REDIRECT_URI
        original_naver_redirect_uri = settings.NAVER_REDIRECT_URI
        try:
            settings.KAKAO_REDIRECT_URI = "https://ongaji.site/api/v1/auth/oauth/kakao/callback"
            settings.OAUTH_REDIRECT_URI = "https://legacy.example.com/auth/callback/kakao"
            settings.NAVER_REDIRECT_URI = "https://ongaji.site/api/v1/auth/oauth/naver/callback"

            kakao_url = self.client.get("/api/v1/auth/login/kakao").json()["auth_url"]
            kakao_query = parse_qs(urlparse(kakao_url).query)
            self.assertEqual(
                kakao_query["redirect_uri"][0],
                "https://ongaji.site/api/v1/auth/oauth/kakao/callback",
            )

            settings.KAKAO_REDIRECT_URI = ""
            fallback_url = self.client.get("/api/v1/auth/login/kakao").json()["auth_url"]
            fallback_query = parse_qs(urlparse(fallback_url).query)
            self.assertEqual(
                fallback_query["redirect_uri"][0],
                "https://legacy.example.com/auth/callback/kakao",
            )

            naver_url = self.client.get("/api/v1/auth/login/naver").json()["auth_url"]
            naver_query = parse_qs(urlparse(naver_url).query)
            self.assertEqual(
                naver_query["redirect_uri"][0],
                "https://ongaji.site/api/v1/auth/oauth/naver/callback",
            )
        finally:
            settings.KAKAO_REDIRECT_URI = original_kakao_redirect_uri
            settings.OAUTH_REDIRECT_URI = original_oauth_redirect_uri
            settings.NAVER_REDIRECT_URI = original_naver_redirect_uri

    def test_kakao_oauth_callback_creates_social_user_and_tokens(self):
        original_kakao_client_id = settings.KAKAO_CLIENT_ID
        original_kakao_rest_api_key = settings.KAKAO_REST_API_KEY
        try:
            settings.KAKAO_CLIENT_ID = ""
            settings.KAKAO_REST_API_KEY = "kakao-rest-key"
            with patch(
                "app.api.v1.auth.service._post_form",
                return_value={
                    "access_token": "provider-access",
                    "refresh_token": "provider-refresh",
                    "expires_in": 3600,
                },
            ), patch(
                "app.api.v1.auth.service._get_json",
                return_value={
                    "id": 12345,
                    "kakao_account": {
                        "email": "kakao@example.com",
                        "profile": {"nickname": "카카오사용자"},
                    },
                },
            ):
                response = self.client.get("/api/v1/auth/oauth/kakao/callback", params={"code": "abc"})

            self.assertEqual(response.status_code, 200)
            token_payload = decode_token(response.json()["access_token"])
            self.assertEqual(token_payload["role"], "user")
            self.assertEqual(token_payload["provider"], "kakao")

            db = self.SessionLocal()
            try:
                account = db.query(SocialAccount).filter_by(provider="kakao", provider_user_id="12345").one()
                user = db.get(User, account.user_id)
                self.assertEqual(user.email, "kakao@example.com")
                self.assertIsNone(user.password_hash)
                self.assertEqual(account.access_token, "provider-access")
                self.assertEqual(account.refresh_token, "provider-refresh")
                self.assertIsNotNone(account.token_expires_at)
            finally:
                db.close()
        finally:
            settings.KAKAO_CLIENT_ID = original_kakao_client_id
            settings.KAKAO_REST_API_KEY = original_kakao_rest_api_key

    def test_naver_oauth_callback_updates_existing_social_account(self):
        db = self.SessionLocal()
        user = User(
            email="naver@example.com",
            password_hash=None,
            nickname="사용자777",
            role=UserRole.USER,
        )
        db.add(user)
        db.flush()
        account = SocialAccount(
            user_id=user.id,
            provider="naver",
            provider_user_id="naver-1",
            access_token="old-access",
            refresh_token="old-refresh",
        )
        db.add(account)
        db.commit()
        db.close()

        original_naver_client_id = settings.NAVER_CLIENT_ID
        try:
            settings.NAVER_CLIENT_ID = "naver-client"
            with patch(
                "app.api.v1.auth.service._post_form",
                return_value={
                    "access_token": "new-access",
                    "expires_in": 1800,
                },
            ), patch(
                "app.api.v1.auth.service._get_json",
                return_value={
                    "response": {
                        "id": "naver-1",
                        "email": "naver@example.com",
                        "nickname": "네이버사용자",
                    },
                },
            ):
                response = self.client.get(
                    "/api/v1/auth/oauth/naver/callback",
                    params={"code": "abc", "state": "state"},
                )

            self.assertEqual(response.status_code, 200)
            token_payload = decode_token(response.json()["access_token"])
            self.assertEqual(token_payload["role"], "user")
            self.assertEqual(token_payload["provider"], "naver")

            db = self.SessionLocal()
            try:
                updated = db.query(SocialAccount).filter_by(provider="naver", provider_user_id="naver-1").one()
                self.assertEqual(updated.access_token, "new-access")
                self.assertEqual(updated.refresh_token, "old-refresh")
                self.assertIsNotNone(updated.token_expires_at)
            finally:
                db.close()
        finally:
            settings.NAVER_CLIENT_ID = original_naver_client_id


if __name__ == "__main__":
    unittest.main()
