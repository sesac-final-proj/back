# 어드민 (admin) — 1순위 범위

> 브랜치: `feat/admin`
> 우선순위: 1순위 (AD-01, AD-02) / AD-03(기부 관리)은 [09-backlog-2nd-3rd.md](09-backlog-2nd-3rd.md)
> API prefix: `/api/v1/admin` (태그: `어드민`)
> 관련 문서: [API_DESIGN.md](../API_DESIGN.md) "어드민" 절

## 개요

데이터 수집현황·오류관리, 공지관리. 전체 엔드포인트에 `Depends(require_admin)` 적용.

## 선행 조건

- [02-auth.md](02-auth.md) 완료 (`require_admin` Dependency)
- [05-local.md](05-local.md)의 공지 수집 파이프라인(TASK-04-01) — AD-02가 이 데이터를 다룸
- [03-trades.md](03-trades.md)의 `Transaction` 적재 — AD-01이 이 데이터 현황을 다룸

## Task 목록

### TASK-03-01: 데이터 수집현황 대시보드 — `GET /api/v1/admin/data-status` 🔒(admin)

- [ ] 상품/지역별 수집 데이터 건수 집계 (`Transaction` 카운트 by region)
- [ ] 수집 오류 상태 표시 — 오류 로그를 저장할 최소 테이블 필요 시 `CollectionError`(source, message, occurred_at) 추가 (없으면 이 TASK에서 신설)
- 완료조건(DoD): admin 토큰으로 접근 시 지역별 건수 + 최근 오류 목록 반환, 일반 user 토큰은 403

### TASK-03-02: 공지 목록 조회 — `GET /api/v1/admin/notices` 🔒(admin)

- [ ] [05-local.md](05-local.md)의 `LocalNotice` 테이블을 관리자 관점으로 목록 조회 (필터: 지역, 유형, 상태)
- 완료조건(DoD): 페이지네이션 포함 목록 반환

### TASK-03-03: 공지 상태 변경 — `PATCH /api/v1/admin/notices/{notice_id}/status` 🔒(admin)

- [ ] 상태값 정의 (예: `draft` / `published` / `hidden`)
- [ ] 존재하지 않는 notice_id → 404
- 완료조건(DoD): 상태 변경 후 일반 사용자 API(`GET /local/notices`)에 즉시 반영

### TASK-03-04: 알림 생성 — `POST /api/v1/admin/notices/{notice_id}/alert` 🔒(admin)

- [ ] 최초 구현 범위: 알림 발송 자체(푸시/SMS 등 외부 연동)는 범위 밖 — "알림 대상 생성" 수준까지만 (예: `Alert` row 적재)
- [ ] 실제 발송 채널 연동은 별도 이슈로 분리 (범위 명확히: 이 TASK는 발송 트리거 API까지만)
- 완료조건(DoD): 호출 시 `Alert` 레코드 생성, 대상 notice 없으면 404

## 비고

- AD-03(기부 내역 검수, 2순위)은 [09-backlog-2nd-3rd.md](09-backlog-2nd-3rd.md)에서 다룬다.
