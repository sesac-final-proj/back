# 회원관리 (auth)

> 브랜치: `feat/auth`
> 우선순위: 1순위
> API prefix: `/api/v1/auth` (태그: `회원관리`)
> 관련 문서: [API_DESIGN.md](../API_DESIGN.md) "회원관리" 절

## 개요

회원가입, 로그인, JWT 인증, 활동동네 설정, 사용자 Role 관리. 다른 모든 EPIC이 `Depends(get_current_user)`에 의존하므로 가장 먼저 완성돼야 한다.

## 선행 조건

- [01-common-infra.md](01-common-infra.md) 전체 완료 (`User`, `Region` 모델 + JWT Dependency)

## 데이터 모델

- `User`: `id`, `email`(unique), `password_hash`, `nickname`, `role`(`user`/`admin`), `created_at`
- `UserRegion` (또는 `User.region_id` 단일 FK — TASK-00-03에서 결정한 구조 따름): 활동동네, 거래반경(`radius_m` 등)

## Task 목록

### TASK-01-01: 회원가입 — `POST /api/v1/auth/signup`

- [ ] `schema.SignupRequest`(email, password, nickname) / `schema.SignupResponse`
- [ ] 이메일 중복 검사 → 409 Conflict
- [ ] 비밀번호 정책: 최소 길이 등 최소한의 검증 (과설계 금지, 8자 이상 정도)
- [ ] 비밀번호는 반드시 해시 저장 (평문 저장 금지 — 보안 필수 항목)
- 완료조건(DoD): 정상 가입 201, 이메일 중복 409, 잘못된 형식(이메일 아님/비밀번호 짧음) 422

### TASK-01-02: 로그인 — `POST /api/v1/auth/login`

- [ ] `schema.LoginRequest`(email, password) / `schema.TokenResponse`(access_token, refresh_token, token_type)
- [ ] 이메일/비밀번호 불일치 시 401 (이메일 존재 여부를 노출하지 않도록 메시지 통일)
- [ ] Refresh Token 저장 방식 결정: DB 테이블(`RefreshToken`) 또는 Redis 중 하나 — 초기엔 DB 테이블로 단순하게 (Redis는 트래픽 생기면 고려)
- 완료조건(DoD): 정상 로그인 시 access/refresh 토큰 발급, 실패 시 401

### TASK-01-03: 로그아웃 — `POST /api/v1/auth/logout` 🔒

- [ ] 전달받은 Refresh Token을 DB에서 폐기(삭제 또는 `revoked=true` 플래그)
- 완료조건(DoD): 로그아웃 후 해당 refresh token으로 `/refresh` 호출 시 401

### TASK-01-04: 토큰 갱신 — `POST /api/v1/auth/refresh`

- [ ] Refresh Token 검증 (만료/폐기 여부 포함) → 새 Access Token 발급
- [ ] Refresh Token 자체가 만료/위조면 401
- 완료조건(DoD): 유효한 refresh token으로 새 access token 발급, 만료된 refresh token은 401

### TASK-01-05: 내 정보 조회 — `GET /api/v1/auth/me` 🔒

- [ ] `schema.MeResponse`(id, email, nickname, role, region 정보 포함)
- 완료조건(DoD): 인증 성공 시 본인 정보 반환, 토큰 없으면 401

### TASK-01-06: 활동동네·거래반경 설정 — `PUT /api/v1/auth/me/region` 🔒

- [ ] `schema.RegionUpdateRequest`(region_id 또는 dong_code, radius_m)
- [ ] 존재하지 않는 `region_id` → 404
- [ ] PRD 기준 초기 지원 지역은 영등포/노원/송파 3개 — 이 외 지역 코드가 들어와도 서버는 `Region` 테이블에 있으면 허용 (하드코딩 3개로 제한하지 않음, 데이터로 관리)
- 완료조건(DoD): 정상 변경 200, 잘못된 region_id 404

### TASK-01-07: 마이페이지 요약 — `GET /api/v1/auth/me/summary` 🔒

- [ ] 활동동네, 거래내역 요약(건수), 포인트 잔액을 한 번에 반환
- [ ] 거래내역은 `trades` EPIC, 포인트는 `dream` EPIC 데이터에 의존 → 해당 EPIC의 서비스 함수를 import해서 조합 (직접 DB 조인 대신 서비스 레이어 호출로 결합도 관리)
- 완료조건(DoD): 다른 EPIC 미구현 상태에서도 501/빈 값으로 안전하게 응답 (하드 의존으로 500 나지 않게)
- 참고: 다른 EPIC이 먼저 구현되기 전까지는 스텁으로 두고, `docs/issue/09-backlog-2nd-3rd.md`가 아니라 이 파일에서 후속 연동 TASK로 이어감

## 비고 (권한관리)

- 별도 "권한 조회/변경 API"는 만들지 않는다. Role은 `User.role` 컬럼 + `Depends(require_admin)`으로 충분 (API_DESIGN.md 방침). admin 승격은 DB 직접 조작 또는 시드 스크립트로 처리 (관리자 승격 API가 필요해지면 그때 추가).
