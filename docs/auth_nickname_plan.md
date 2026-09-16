# 인증/관리자/닉네임 구현 현황 및 환경 분리 계획

## 개요

현재 백엔드는 FastAPI 기반으로 카카오/네이버 소셜 로그인, JWT access/refresh token, 로그아웃, DB 기반 관리자 인증, 닉네임 추천/검증 기능을 제공한다.

프론트는 Next.js 테스트 화면으로 일반 로그인, 관리자 로그인, 관리자 비밀번호 변경, 로그인 후 닉네임 설정 흐름을 확인할 수 있다.

이번 문서는 기존 구현 현황과 앞으로 적용할 개발/운영 환경 분리, 금칙어 데이터 외부화 계획을 함께 정리한다.

## 실행 URL

- 일반 로그인 화면: `http://localhost:3000`
- 닉네임 설정 화면: `http://localhost:3000/profile/nickname`
- 관리자 화면: `http://localhost:3000/admin`
- 관리자 비밀번호 변경 화면: `http://localhost:3000/admin/password`
- Swagger: `http://localhost:8000/docs`
- Backend base URL: `http://localhost:8000`

## 주요 실행 명령

```powershell
alembic upgrade head
python -m uvicorn main:app --host localhost --port 8000
```

```powershell
cd frontend
npm.cmd run dev -- --hostname localhost --port 3000
```

## 소셜 로그인

지원 provider:

- `kakao`
- `naver`

주요 API:

- `GET /auth/login/kakao`
- `GET /auth/login/naver`
- `GET /auth/callback/kakao`
- `GET /auth/callback/naver`
- `POST /auth/refresh`
- `POST /auth/logout`

로그인 성공 시 백엔드가 자체 JWT를 발급한다.

일반 사용자 JWT claim:

```json
{
  "sub": "<provider user id>",
  "role": "user",
  "provider": "kakao 또는 naver",
  "type": "access 또는 refresh",
  "jti": "...",
  "iat": 0,
  "exp": 0
}
```

카카오 로그인 URL에는 `prompt=login`, 네이버 로그인 URL에는 `auth_type=reauthenticate`를 붙여 자동 로그인 완화를 시도한다.

## Refresh/Logout

refresh token rotation을 적용한다.

흐름:

```text
refresh token 검증
→ 저장소의 현재 jti 확인
→ 새 access/refresh token 발급
→ 새 refresh jti 저장
→ 기존 refresh token revoke
```

refresh token 저장소:

- `REDIS_URL`이 있으면 Redis 사용
- 없으면 개발용 메모리 fallback 사용

로그아웃 시 access/refresh token을 revoke하고 refresh 세션을 삭제한다.

## 관리자 인증

관리자 계정은 `.env` 고정값이 아니라 DB `admins` 테이블에서 관리한다.

관리자 비밀번호 원문은 저장하지 않고 Argon2 hash만 저장한다.

관리자 JWT claim:

```json
{
  "sub": "<admin id>",
  "role": "admin",
  "provider": "local",
  "type": "access 또는 refresh",
  "jti": "...",
  "iat": 0,
  "exp": 0
}
```

주요 API:

- `POST /auth/admin/login`
- `POST /auth/admin/refresh`
- `POST /auth/admin/logout`
- `GET /auth/admin/me`
- `POST /auth/admin/password`

관리자 전용 API는 `require_admin` dependency로 `role="admin"`을 검증한다.

## 최초 관리자 생성

관리자 계정은 DB에 생성해야 로그인할 수 있다.

```powershell
python -m app.scripts.create_admin --email admin@example.com --name "관리자"
```

비밀번호는 터미널 프롬프트로 입력한다. 비밀번호 원문은 소스코드, `.env`, 로그에 남기지 않는다.

## DB/Migration

Alembic을 도입했다.

현재 migration:

- `20260831_0001_create_admins.py`: `admins` 테이블 생성
- `20260831_0002_create_users.py`: `users` 테이블 생성, `nickname` unique 적용

주요 DB 제약:

- `admins.email` unique
- `users.nickname` unique

## 닉네임 정책

닉네임 정책:

- 최대 7자
- 빈 문자열 금지
- 한글 허용
- 숫자 `0~9` 허용
- 한글 + 숫자 조합 허용
- 숫자로만 구성된 닉네임 금지
- 영어 금지
- 특수문자 금지
- 공백 금지
- 금칙어 포함 금지
- 중복 닉네임 금지

예시:

- 허용: `수달`, `수달1`, `나는공주1`, `토끼777`
- 거부: `12345`, `Happy수달`, `수달!`, `포근한 수달`

오류 코드:

- `NICKNAME_REQUIRED`: 닉네임을 입력해주세요.
- `NICKNAME_TOO_LONG`: 닉네임은 7자 이하로 입력해주세요.
- `NICKNAME_CONTAINS_SPACE`: 공백 없이 입력해주세요.
- `NICKNAME_INVALID_CHARACTERS`: 한글과 숫자만 입력해주세요.
- `NICKNAME_REQUIRES_KOREAN`: 한글을 포함해주세요.
- `NICKNAME_FORBIDDEN`: 사용할 수 없는 표현이 포함되어 있어요.
- `NICKNAME_ALREADY_EXISTS`: 이미 사용 중인 닉네임이에요.
- `NICKNAME_RECOMMENDATION_FAILED`: 원하는 닉네임을 직접 입력해주세요.

## 닉네임 API

추천:

```http
GET /api/v1/nicknames/recommendation
```

응답:

```json
{
  "nickname": "포근한수달"
}
```

사용 가능 여부:

```http
GET /api/v1/nicknames/availability?nickname=나는공주1
```

응답:

```json
{
  "available": true,
  "code": "NICKNAME_AVAILABLE",
  "message": "사용 가능한 닉네임이에요."
}
```

최종 저장:

```http
POST /api/v1/nicknames/selection
Authorization: Bearer <access_token>
```

```json
{
  "nickname": "나는공주1"
}
```

최종 저장 시에도 다시 검증하고, DB unique 제약조건으로 중복 저장을 방지한다.

## 닉네임 설정 UX

소셜 로그인 성공 후 `/profile/nickname`으로 이동한다.

흐름:

```text
페이지 진입
→ 추천 API 자동 호출
→ 추천 닉네임 입력칸에 표시
→ 재추천 아이콘 첫 클릭 시 두 번째 추천 호출
→ 재추천 아이콘 두 번째 클릭 시 직접 입력 모드 전환
→ 직접 입력 중 프론트 형식 검증
→ 형식 통과 시 debounce 후 availability API 호출
→ 사용 가능할 때만 저장 가능
```

프론트는 API 실패 raw JSON을 그대로 노출하지 않고 사용자용 메시지로 변환한다.

## 현재 환경설정 구조

현재 루트에는 `.env`만 존재한다.

```text
.env
.gitignore
app/core/config.py
nickname/resources/forbidden_words.json
nickname/resources/nickname_words.json
```

현재 `.env.local`, `.env.prod`, `.env.example`은 없다.

검색 결과 현재 프로젝트 루트에서 Dockerfile 또는 docker-compose 파일은 확인되지 않았다.

현재 설정은 `app/core/config.py`에서 `pydantic-settings`를 사용한다.

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8-sig")
```

즉 현재는 `.env` 하나만 고정으로 읽고, Local / Production 구분이 없다.

## 현재 금칙어 데이터 구조

현재 실제 금칙어 데이터 위치:

```text
nickname/resources/forbidden_words.json
```

현재 추천 닉네임 단어 데이터 위치:

```text
nickname/resources/nickname_words.json
```

현재 `nickname/resources.py`에서 금칙어 파일 경로가 하드코딩되어 있다.

```python
RESOURCE_DIR = Path(__file__).resolve().parent / "resources"
NICKNAME_WORDS_PATH = RESOURCE_DIR / "nickname_words.json"
FORBIDDEN_WORDS_PATH = RESOURCE_DIR / "forbidden_words.json"
```

`NicknameValidator`는 `load_forbidden_words()`를 통해 이 파일을 읽는다.

```python
class NicknameValidator:
    def __init__(self, forbidden_words: list[str] | None = None) -> None:
        self.forbidden_words = forbidden_words or load_forbidden_words()
```

현재 문제점:

- 금칙어 파일 경로가 코드에 고정되어 있음
- 환경별 금칙어 파일을 바꿀 수 없음
- 실제 금칙어 데이터 파일이 Git에 노출될 수 있음
- 파일이 누락되었을 때 운영환경에서 명확히 감지하는 구조가 아님

## 금칙어 DB 관리 계획

실제 금칙어 목록은 문서나 Git 저장소에 직접 적지 않는다.

초기 MVP에서는 `FORBIDDEN_WORDS_PATH`로 지정한 JSON 파일을 읽어 `NicknameValidator`에서 사용한다. 이후 운영 정책이 확정되면 금칙어 데이터를 DB 테이블로 이관할 수 있다.

권장 전환 흐름:

```text
운영환경에서 주입된 금칙어 JSON
↓
관리자 또는 seed command로 DB 적재
↓
forbidden_words 테이블
↓
NicknameValidator
```

### ForbiddenWord 모델 설계

DB로 전환할 경우 다음 테이블을 추가한다.

```text
forbidden_words
```

권장 컬럼:

```text
id
word
is_active
created_at
updated_at
created_by
updated_by
```

권장 제약조건:

- `word` unique
- `word` not null
- `is_active` default true

`word`에는 실제 금칙어 문자열이 저장된다. 단, 이 데이터는 운영 DB에만 존재해야 하며 Git에 포함하지 않는다.

### DB 기반 검증 방식

DB 전환 후 `NicknameValidator`는 파일을 직접 읽지 않고 `ForbiddenWordRepository` 또는 별도 service를 통해 활성 금칙어 목록을 가져온다.

구조:

```text
Router
↓
NicknameService
↓
NicknameValidator
↓
ForbiddenWordRepository
↓
Database
```

성능을 고려하면 매 요청마다 DB를 직접 조회하지 않고 캐시를 둘 수 있다.

권장 캐시 방식:

- local/dev: 프로세스 메모리 cache
- prod: Redis cache 또는 애플리케이션 cache
- 관리자에서 금칙어 변경 시 cache invalidation

### 금칙어 DB 적재 방식

실제 금칙어 데이터를 문서에 넣지 않고, 배포 환경에서 주입된 파일을 DB로 적재한다.

예시 명령:

```powershell
python -m app.scripts.import_forbidden_words --path C:\secure\forbidden_words.json
```

운영 예시:

```bash
python -m app.scripts.import_forbidden_words --path /run/secrets/forbidden_words.json
```

적재 정책:

- 동일 단어가 이미 있으면 중복 insert 하지 않음
- 기존 단어는 유지
- 필요 시 비활성화 정책은 별도 옵션으로 처리
- import 로그에는 실제 금칙어 원문을 출력하지 않음
- 총 적재 개수, 신규 개수, 중복 개수만 출력

### 관리자 화면 확장 가능성

추후 관리자 대시보드에서 금칙어 관리 기능을 추가할 수 있다.

가능한 기능:

- 금칙어 목록 조회
- 금칙어 추가
- 금칙어 비활성화
- 금칙어 재활성화
- 금칙어 변경 이력 확인

이 경우에도 실제 금칙어 데이터는 Git에 포함하지 않고 DB에서만 관리한다.

### DB 전환 시 migration 계획

Alembic migration을 추가한다.

```text
YYYYMMDD_0003_create_forbidden_words.py
```

생성 대상:

- `forbidden_words` 테이블
- `word` unique index
- `is_active` index

마이그레이션에는 실제 금칙어 데이터를 넣지 않는다.

실제 데이터는 별도 import command 또는 운영 관리자 기능으로 넣는다.

### DB 전환 시 테스트 계획

추가 테스트:

- 금칙어 생성
- 금칙어 중복 생성 방지
- 비활성 금칙어는 검증에서 제외
- 활성 금칙어 포함 닉네임 차단
- 정상 닉네임 허용
- import command가 JSON 파일을 DB에 적재
- import command가 중복 단어를 중복 저장하지 않음
- import command 로그에 실제 금칙어 원문이 노출되지 않음
- 캐시 사용 시 금칙어 변경 후 cache invalidation 동작

## 현재 .gitignore 상태

현재 `.gitignore` 내용:

```gitignore
__pycache__/
*.py[cod]
.venv/
.env
*.egg-info/
.pytest_cache/
.mypy_cache/
.DS_Store
```

현재 제외되지 않는 항목:

- `.env.local`
- `.env.prod`
- `nickname/resources/forbidden_words.json`
- `nickname/resources/forbidden_words.local.json`
- `nickname/resources/forbidden_words.prod.json`

현재 작업 경로에서는 Git 저장소가 확인되지 않았다.

```text
fatal: not a git repository
```

따라서 이 환경에서는 `nickname/resources/forbidden_words.json`이 이미 Git에 추적 중인지 확인할 수 없다.

이미 Git에 추적 중이라면 `.gitignore`에 추가하는 것만으로는 부족하다.

```bash
git rm --cached nickname/resources/forbidden_words.json
```

위 명령으로 Git 추적만 제거하고 로컬 파일은 유지해야 한다.

## 환경 분리 목표

```text
개발환경
.env.local
↓
로컬 설정
↓
로컬 금칙어 데이터

운영환경
.env.prod
↓
운영 설정
↓
운영용 금칙어 데이터

              ↓
      동일한 백엔드 코드
              ↓
      NicknameValidator
```

## 변경할 파일 목록

수정 대상 파일:

```text
app/core/config.py
nickname/resources.py
.gitignore
README.md
tests/test_nickname.py
```

추가 대상 파일:

```text
.env.example
nickname/resources/forbidden_words.example.json
```

## Local 환경 금칙어 로딩 방식

권장 구조:

```text
.env.local
↓
FORBIDDEN_WORDS_PATH=nickname/resources/forbidden_words.local.json
↓
NicknameValidator
```

개발자는 예시 파일을 복사해서 실제 로컬 금칙어 파일을 만든다.

```text
nickname/resources/forbidden_words.example.json
↓ 복사
nickname/resources/forbidden_words.local.json
↓ 실제 로컬 금칙어 입력
```

실제 금칙어 파일은 Git에 커밋하지 않는다.

## Production 환경 금칙어 로딩 방식

권장 구조:

```text
.env.prod
↓
FORBIDDEN_WORDS_PATH=/run/secrets/forbidden_words.json
↓
운영 서버 또는 배포 시스템에서 파일 주입
↓
NicknameValidator
```

운영환경에서는 실제 금칙어 데이터를 Git이나 Docker image 안에 넣지 않는다.

추후 운영 방식에 따라 다음 방식으로 확장할 수 있다.

- Docker volume mount
- CI/CD secret file injection
- 서버의 별도 보안 디렉터리
- Secret Manager
- S3 또는 외부 스토리지

현재 단계에서는 외부 시스템을 추가하지 않고 `환경변수 → 파일 경로 → JSON 로딩` 구조가 적절하다.

## 파일 누락 또는 JSON 오류 처리

### Production

운영환경에서는 금칙어 데이터 로딩 실패를 조용히 넘기지 않는다.

다음 경우 애플리케이션 시작 단계에서 명확한 설정 오류를 발생시킨다.

- `FORBIDDEN_WORDS_PATH`가 비어 있음
- 파일이 존재하지 않음
- JSON 형식이 잘못됨
- `forbidden_words`가 list가 아님

### Local

로컬환경에서는 다음 방식을 권장한다.

- `FORBIDDEN_WORDS_PATH`가 설정되어 있으면 해당 파일을 반드시 읽는다.
- 설정된 파일이 없거나 JSON이 잘못되면 명확한 오류를 발생시킨다.
- `FORBIDDEN_WORDS_PATH`가 아예 없을 경우에만 예시 파일 fallback을 둘 수 있다.

단, 금칙어 검증이 무력화되는 것을 피하기 위해 빈 목록으로 조용히 실행하지 않는다.

### Test

테스트는 실제 운영/로컬 금칙어 파일에 의존하지 않는다.

테스트용 임시 JSON fixture를 만들고 `FORBIDDEN_WORDS_PATH`를 해당 fixture로 지정한다.

## 권장 .gitignore 변경안

```gitignore
.env
.env.local
.env.prod

nickname/resources/forbidden_words.json
nickname/resources/forbidden_words.local.json
nickname/resources/forbidden_words.prod.json
!nickname/resources/forbidden_words.example.json
```

운영/로컬 금칙어 실제 파일은 제외하고, 예시 파일만 Git에 포함한다.

## 권장 .env.example 예시

```env
APP_ENV=local
FORBIDDEN_WORDS_PATH=nickname/resources/forbidden_words.local.json

DB_USER=
DB_PASSWORD=
DB_HOST=localhost
DB_PORT=5432
DB_NAME=postgres

JWT_SECRET_KEY=change-me
JWT_ALGORITHM=HS256
REDIS_URL=
```

실제 `.env.local`, `.env.prod`에는 secret 값이 들어갈 수 있으므로 Git에 커밋하지 않는다.

## 테스트 계획

추가 또는 수정할 테스트:

- Local 설정 정상 로딩
- Production 설정 정상 로딩
- `FORBIDDEN_WORDS_PATH` 기반 금칙어 JSON 로딩
- 금칙어 포함 닉네임 차단
- 정상 닉네임 허용
- 잘못된 JSON 처리
- 존재하지 않는 파일 처리
- Production에서 금칙어 데이터 누락 시 오류 발생
- 실제 금칙어 데이터 파일이 `.gitignore` 대상인지 확인
- 기존 닉네임 추천 API 정상 동작
- 기존 닉네임 availability API 정상 동작
- 기존 닉네임 selection API 정상 동작
- 기존 인증 테스트 정상 동작

기존 테스트 중 `load_forbidden_words()`가 실제 `nickname/resources/forbidden_words.json`에 의존하는 부분은 테스트 fixture 기반으로 변경한다.

## 주요 파일

백엔드:

- `main.py`
- `app/auth/router.py`
- `app/auth/service.py`
- `app/auth/admin_service.py`
- `app/auth/admin_repository.py`
- `app/auth/models.py`
- `app/auth/password_service.py`
- `app/auth/token_service.py`
- `app/auth/refresh_store.py`
- `app/auth/dependencies.py`
- `app/scripts/create_admin.py`
- `app/core/config.py`
- `nickname/router.py`
- `nickname/service.py`
- `nickname/validator.py`
- `nickname/repository.py`
- `nickname/errors.py`
- `nickname/resources.py`
- `nickname/resources/nickname_words.json`
- `nickname/resources/forbidden_words.json`

프론트:

- `frontend/app/page.tsx`
- `frontend/app/auth/callback/page.tsx`
- `frontend/app/profile/nickname/page.tsx`
- `frontend/app/admin/page.tsx`
- `frontend/app/admin/password/page.tsx`
- `frontend/lib/auth/client.ts`
- `frontend/lib/auth/storage.ts`
- `frontend/lib/auth/use-social-auth.ts`
- `frontend/lib/auth/use-admin-auth.ts`

테스트:

- `tests/test_auth.py`
- `tests/test_nickname.py`

## 구현 순서

다음 단계에서 실제 구현 시에는 아래 순서로 진행한다.

1. `app/core/config.py`에 환경 구분 설정 추가
2. `FORBIDDEN_WORDS_PATH` 설정 추가
3. `nickname/resources.py`에서 금칙어 경로 하드코딩 제거
4. 금칙어 파일 로딩 실패를 명확한 오류로 처리
5. `forbidden_words.example.json` 추가
6. 실제 금칙어 파일 `.gitignore` 처리
7. README에 로컬/운영 설정 방법 추가
8. 테스트를 fixture 기반으로 수정
9. 기존 인증/닉네임 테스트 회귀 확인

## 검증 명령

```powershell
python -m pytest tests\test_auth.py tests\test_nickname.py
```

```powershell
cd frontend
npm.cmd run build
```

마지막 확인 기준:

```text
tests/test_auth.py + tests/test_nickname.py 통과
frontend build 성공
```
### Windows 환경 테스트 주의사항
- Windows 환경에서는 `uvloop` 패키지가 지원되지 않아 `pip install -r requirements.txt` 시 설치 에러가 발생할 수 있습니다.
- 로컬 테스트 및 검증 시에는 테스트 관련 필수 패키지(`pytest`, `httpx`, `fastapi`, `pydantic-settings`, `alembic`, `passlib`, `argon2-cffi`, `python-jose` 등)만 별도 설치하여 검증을 진행합니다.

**검증 명령**
```bash
python -m pytest tests/test_auth.py tests/test_nickname.py
cd frontend
npm.cmd run build