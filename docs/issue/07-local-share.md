# 지역상생 (local_share)

> 브랜치: `feat/local-share`
> 우선순위: 1순위
> API prefix: `/api/v1/local-share` (태그: `지역상생`)
> 관련 문서: [API_DESIGN.md](../API_DESIGN.md) "지역상생" 절

## 개요

기부금 사용결과, 지역 소상공인 집행내역, 지역 환류율을 공개한다. 전부 공개 API(인증 불필요) — 신뢰 확보가 목적이므로 로그인 없이도 누구나 볼 수 있어야 한다.

## 선행 조건

- [06-dream.md](06-dream.md)의 `Donation` 데이터 존재

## 데이터 모델

- `MerchantSpend`: `id`, `facility_id`(또는 지역 단위), `merchant_name`, `amount`, `region_id`, `spent_at`, `description`(집행 내역 설명)

## Task 목록

### TASK-06-01: 기부금 사용결과 공개 — `GET /api/v1/local-share/results`

- [ ] `Donation` + `MerchantSpend`를 조합해 "얼마가 모여서 어디에 어떻게 쓰였는지" 형태로 반환
- [ ] 지역(`region`) 필터 지원
- 완료조건(DoD): 데이터 없는 지역도 빈 배열로 정상 응답 (500 아님)

### TASK-06-02: 지역 소상공인 집행내역 — `GET /api/v1/local-share/merchant-spends`

- [ ] `MerchantSpend` 목록 조회 (지역/기간 필터)
- [ ] 집행내역 데이터 입력 경로 결정 필요: 관리자 수동 입력 API가 아직 없음 → 최소한 [04-admin.md](04-admin.md)에 `POST /admin/merchant-spends` 추가가 필요한지 이 TASK 착수 시 확인 (현재 API_DESIGN.md에는 없음 — 없으면 시드 데이터로 대체하고 관리 API는 2순위 백로그로 이관)
- 완료조건(DoD): 목록 조회 정상 동작, 데이터 입력 경로에 대한 결정 사항이 PR 설명에 명시됨

### TASK-06-03: 지역 환류율 — `GET /api/v1/local-share/circulation-rate`

- [ ] PRD 5절 공식 구현: `지역 소상공인 집행금액 ÷ 전체 지원금 × 100`
- [ ] "전체 지원금"의 정의 확정 필요: 해당 지역 누적 `Donation` 총액 기준으로 계산 (다른 정의가 필요하면 PR에서 근거 명시)
- [ ] 분모가 0인 경우(아직 기부금 없음) → 0% 또는 `null` + 명확한 메시지로 반환 (ZeroDivisionError로 500 나지 않게)
- 완료조건(DoD): 분모 0 케이스 포함 단위테스트, 정상 케이스는 소수점 반올림 기준 통일(예: 소수 1자리)
