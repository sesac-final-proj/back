# 꿈가지 (dream)

> 브랜치: `feat/dream`
> 우선순위: 1순위
> API prefix: `/api/v1/dream` (태그: `꿈가지`)
> 관련 문서: [API_DESIGN.md](../API_DESIGN.md) "꿈가지" 절, PRD 5절 "꿈가지" Flow

## 개요

거래/결제 시 포인트 적립 → 기부금 설정 → 기부처 선택 → 기부 → 사용결과 공개. Flow: `거래/결제 → 포인트 적립 → 기부금 설정 → 기부처 선택 → 기부 → 사용결과 공개`

## 선행 조건

- [02-auth.md](02-auth.md) 완료
- [03-trades.md](03-trades.md)의 거래 완료 이벤트 (포인트 적립 트리거)

## 데이터 모델

- `PointAccount`: `user_id`, `balance`
- `PointTransaction`: `id`, `user_id`, `amount`, `source`(general_payment/trade), `related_id`(거래/결제 id), `created_at`
- `Facility`: 지원시설(기부처) — `id`, `name`, `region_id`, `description`
- `DonationSetting`: `user_id`, `donation_rate`(비율), `facility_id`(선택 기부처)
- `Donation`: `id`, `user_id`, `facility_id`, `amount`, `created_at`

## Task 목록

### TASK-05-01: 포인트 적립 (내부 호출) — `POST /api/v1/dream/points/accrue` 🔒

- [ ] PRD 5절 적립 기준 구현:
  | 유형 | 적립률/조건 |
  | --- | --- |
  | 일반결제 | 1% |
  | 중고거래 | 0.1% |
  | 중고거래 | 5,000원 이상 거래에만 적용 |
- [ ] 이 API는 외부(프론트) 직접 호출용이 아니라 결제/거래 완료 시점에 내부적으로 호출되는 것을 전제 — 호출 주체 검증(내부 서비스 키 또는 관리자/시스템 권한) 필요, 아무 사용자나 자기 포인트를 임의로 적립시키지 못하게 막는다 (보안 필수 항목)
- [ ] 적립률/최소금액 기준은 상수로 분리해 변경 용이하게 (하드코딩 산개 금지)
- 완료조건(DoD): 5,000원 미만 중고거래는 적립 없음, 5,000원 이상은 0.1% 적립, 일반결제는 1% 적립 — 3가지 케이스 단위테스트

### TASK-05-02: 내 포인트 조회 — `GET /api/v1/dream/points/me` 🔒

- [ ] 잔액 + 적립 내역(페이지네이션) 반환
- 완료조건(DoD): 신규 사용자는 잔액 0, 적립 이력 없이도 200 응답 (빈 배열)

### TASK-05-03: 기부처 목록 조회 — `GET /api/v1/dream/facilities`

- [ ] 인증 불필요(공개 API) — 지역 필터(`region` 쿼리) 지원
- 완료조건(DoD): 지역 필터 시 해당 지역 시설만, 필터 없으면 전체 반환

### TASK-05-04: 기부 비율/기부처 설정 — `PUT /api/v1/dream/donation-settings` 🔒

- [ ] `schema.DonationSettingRequest`(donation_rate, facility_id)
- [ ] `facility_id`가 `Facility`에 없으면 404
- [ ] `donation_rate` 범위 검증(0~100%) — Pydantic validator로 처리
- 완료조건(DoD): 정상 설정 200, 잘못된 facility_id 404, 범위 밖 비율 422

### TASK-05-05: 기부 실행 로직

- [ ] 포인트 적립 시점 또는 별도 트리거 시점에 `DonationSetting`에 따라 포인트 일부를 `Donation`으로 전환하는 로직 위치 결정 (TASK-05-01 적립 로직 내부에 이어서 처리 — 별도 배치로 분리할 근거가 아직 없음)
- [ ] 기부처 미설정 사용자는 기부 skip (전액 포인트로 유지)
- 완료조건(DoD): 기부 설정된 사용자의 적립 시 `Donation` row가 자동 생성됨

### TASK-05-06: 내 기부내역 조회 — `GET /api/v1/dream/donations/me` 🔒

- [ ] 기부처별/시점별 목록, 누적 기부액 요약 포함
- 완료조건(DoD): 페이지네이션 + 누적 합계 반환
