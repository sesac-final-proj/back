# 2·3순위 백로그

> 우선순위: 2순위 / 3순위 (PRD 6절 "MVP 범위" 기준)
> 이 파일의 TASK들은 각 EPIC 1순위 범위가 끝난 뒤 착수한다. 지금 스켈레톤만 잡아두고, 실제 착수 시점에 해당 EPIC 이슈 파일로 옮겨서 세부 TASK로 다시 쪼갠다.

## 2순위

### TR-08: 타 플랫폼 가격 비교 — `GET /api/v1/trades/analyses/{analysis_id}/platform-comparison`

- 소속: [03-trades.md](03-trades.md)
- [ ] 비교 대상 플랫폼 확정 (PRD 언급: 쿠팡 등) — 공식 API 제공 여부 확인 먼저 (크롤링은 약관 위반 소지, 공식 API/제휴 데이터 우선 검토)
- [ ] 외부 API 응답 지연/실패 시 자체 서비스 응답이 느려지지 않도록 타임아웃 + 실패 시 "비교불가" 처리

### BA-02: 구매자 AI 고도화

- 소속: [08-buyer-ai.md](08-buyer-ai.md) TASK-07-02에 이미 포함됨 (중복 생성 방지 차원에서 여기 별도 TASK 만들지 않음)

### AD-03: 어드민 기부 관리

- 소속: [04-admin.md](04-admin.md)
- [ ] `GET /api/v1/admin/donations` — 기부 내역 목록 (지역/시설/기간 필터)
- [ ] `PATCH /api/v1/admin/donations/{donation_id}/review` — 검수 상태 변경 (예: `pending`/`approved`/`rejected`)
- [ ] 검수 상태값과 [06-dream.md](06-dream.md)의 `Donation` 모델에 `review_status` 컬럼 추가 필요

## 3순위 (후순위)

### TR-07: 예상 재판매가격 — `GET /api/v1/trades/analyses/{analysis_id}/resale-estimate`

- 소속: [03-trades.md](03-trades.md)
- [ ] 착수 전 방법론 결정 필요: 시계열 감가 모델? 유사 카테고리 재판매 사례 기반? — PRD에 방법론 명시 없음, 기획 확정 후 진행
- [ ] 1·2순위 기능(가격 Range, 거래빈도)이 안정화된 뒤 그 데이터를 재사용하는 방향으로 설계 (완전히 새로운 파이프라인 만들지 않음)

## 착수 시 체크

- [ ] 착수 시점에 해당 EPIC의 이슈 파일로 TASK를 옮기고, [00-index.md](00-index.md) 표에도 우선순위 갱신 반영
