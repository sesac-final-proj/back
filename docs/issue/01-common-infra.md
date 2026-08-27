# 공통 인프라 (선행 작업)

> 브랜치: `feat/common-infra`
> 우선순위: 선행 (모든 EPIC 착수 전 완료 필요)
> 관련 문서: [API_DESIGN.md](../API_DESIGN.md) 1절, 4절 "다음 단계" 1번

## 개요

`app/` 디렉토리 자체가 없는 상태다. 다른 EPIC 브랜치들이 동시에 착수해도 충돌 없이 진행할 수 있도록, FastAPI 앱 골격 / DB 연결 / 인증 Dependency / 공통 예외처리를 먼저 만든다.

## 선행 조건

없음 (제일 먼저 진행)

## Task 목록

### TASK-00-01: 프로젝트 골격 및 설정

- [ ] `app/main.py` — FastAPI 앱 생성, 라우터 include 자리 확보 (각 EPIC 라우터는 아직 없어도 됨)
- [ ] `app/core/config.py` — `pydantic-settings` 기반 설정 클래스 (`DATABASE_URL`, `JWT_SECRET`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS` 등), `.env` 로드
- [ ] `.env.example` 작성 (실값 커밋 금지)
- [ ] `requirements.txt`에 `pydantic-settings`, `python-jose[cryptography]`(또는 `pyjwt`), `passlib[bcrypt]` 추가
- 완료조건(DoD): `uvicorn app.main:app --reload` 로 서버가 뜨고 `/docs`(Swagger)가 열린다.

### TASK-00-02: DB 연결 및 세션 관리

- [ ] `app/core/db.py` — SQLAlchemy `engine`, `SessionLocal`, `Base` 선언 (PostgreSQL, `psycopg2-binary` 이미 설치돼 있음)
- [ ] `get_db()` Dependency (요청마다 세션 생성/종료)
- [ ] Alembic 도입 — `alembic init`, `alembic/env.py`에서 `Base.metadata` 연결
- [ ] 마이그레이션 실행 스크립트/문서화 (`alembic upgrade head`)
- 완료조건(DoD): 로컬 PostgreSQL에 대해 `alembic upgrade head`가 에러 없이 수행되고, 빈 테이블 상태라도 연결이 확인된다.

### TASK-00-03: 공통 DB 모델 베이스

PRD 8절 핵심 데이터 중 여러 EPIC이 공유하는 두 엔티티를 여기서 먼저 만든다 (나머지 엔티티는 각 EPIC 이슈에서 생성).

- [ ] `app/models/region.py` — `Region` (행정동 코드, 행정동명, 위도/경도, 상위 지역 등)
  - PRD: "영등포·노원·송파" 등 활동동네 단위. 최소 컬럼: `id`, `dong_code`, `dong_name`, `lat`, `lng`
- [ ] `app/models/user.py` — `User` (이메일, 비밀번호 해시, role, 활동동네 FK, 거래반경, 생성일시)
  - `role`: `user` / `admin` 최소 2종 (Enum)
  - 활동동네는 1개 이상 등록 가능한 구조 고려 (PRD: "영등포·노원·송파 활동동네" — 복수 가능성) → 필요 시 `UserRegion` 매핑 테이블로 분리할지 이 TASK에서 결정하고 근거를 커밋 메시지/PR에 남긴다
- [ ] Alembic 마이그레이션 생성 및 적용
- 완료조건(DoD): `User`, `Region` 테이블이 DB에 생성되고, 간단한 seed 스크립트로 행정동 몇 건 insert가 가능하다.

### TASK-00-04: 인증 Dependency

- [ ] `app/core/security.py` — 비밀번호 해시/검증(`passlib`), JWT 생성/검증 함수 (`create_access_token`, `create_refresh_token`, `decode_token`)
- [ ] `app/core/deps.py` — `get_current_user(token: str = Depends(oauth2_scheme), db=Depends(get_db)) -> User`
- [ ] `require_admin(user: User = Depends(get_current_user)) -> User` — `role != admin`이면 403
- [ ] 만료/위조 토큰 → 401 응답 (에러 포맷은 TASK-00-05와 통일)
- 완료조건(DoD): 더미 라우터에 `Depends(get_current_user)`를 걸어 유효 토큰/무효 토큰/토큰 없음 3가지 케이스가 각각 200/401/401로 응답한다.

### TASK-00-05: 공통 예외 처리 및 응답 포맷

- [ ] `app/core/exceptions.py` — 도메인 예외 클래스(예: `NotFoundError`, `PermissionDeniedError`) 정의
- [ ] `app/main.py`에 `@app.exception_handler(...)` 등록 — 일관된 에러 응답 스키마: `{ "code": str, "message": str }`
- [ ] Pydantic `RequestValidationError`(422) 핸들러도 동일 포맷으로 통일
- 완료조건(DoD): 존재하지 않는 리소스 조회 시 500이 아니라 정의된 4xx + 통일 포맷으로 응답한다.

### TASK-00-06: CORS / 로깅 기본 설정

- [ ] `CORSMiddleware` 설정 (프론트 개발 서버 origin 허용, 배포 시 `.env`로 분리)
- [ ] 기본 로깅 설정 (요청 메서드/경로/상태코드/처리시간 로그) — 미들웨어 1개로 충분, 별도 로깅 프레임워크 도입은 보류
- 완료조건(DoD): 요청 1건당 로그 1줄이 콘솔에 남는다.

## 산출물 체크

- [ ] `app/main.py`, `app/core/{config,db,security,deps,exceptions}.py`
- [ ] `app/models/{user,region}.py`
- [ ] `alembic/` 및 최초 마이그레이션
- [ ] `.env.example`
- [ ] `requirements.txt` 갱신
