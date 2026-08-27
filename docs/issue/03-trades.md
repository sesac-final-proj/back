# 중고거래 (trades)

> 브랜치: `feat/trades`
> 우선순위: 1순위 (TR-01~05), TR-06 미정, TR-07/08은 [09-backlog-2nd-3rd.md](09-backlog-2nd-3rd.md)
> API prefix: `/api/v1/trades` (태그: `중고거래`)
> 관련 문서: [API_DESIGN.md](../API_DESIGN.md) "중고거래" 절, PRD 5절 "중고거래" Flow

## 개요

우리 동네 실거래 데이터를 기반으로 유사거래·적정가격·거래빈도·분석근거를 제공한다. Flow: `상품정보 입력 → 유사거래 검색 → 지역 거래빈도 분석 → 적정가격 산출 → 분석근거 제공`

## 선행 조건

- [02-auth.md](02-auth.md) 완료 (인증 필요 API)
- 원천 거래 데이터(`daangn_풀리오.csv` 등) DB 적재 완료 여부 확인 — 없으면 TASK-02-00 먼저 진행

## 데이터 모델

- `Product`: `id`, `title`, `category`, `desired_price`, `region_id`, `created_by`(user), `created_at`
- `Transaction`: 지역별 중고거래 원천 데이터 — `id`, `product_title`, `category`, `price`, `region_id`, `chat_count`, `interest_count`(관심수), `listed_at`(등록시각), `traded_at`(nullable)
- `Analysis`: 분석 요청 1건 — `id`, `product_id`, `region_id`, `status`(pending/done), `created_at`
- `AnalysisResult`: `analysis_id`, `price_min`, `price_max`, `frequency_grade`, `sample_count`, `evidence_json`

## Task 목록

### TASK-02-00: 거래 원천 데이터 적재 (선행)

- [ ] `Transaction` 테이블 설계/마이그레이션
- [ ] CSV → DB 적재 스크립트 (`scripts/seed_transactions.py` 등, 1회성 — 별도 배치 프레임워크 도입 금지)
- 완료조건(DoD): 로컬 DB에 원천 거래 데이터가 존재하고 `region_id`, `category` 기준으로 조회 가능

### TASK-02-01: 분석 요청 생성 — `POST /api/v1/trades/analyses` 🔒

- [ ] `schema.AnalysisRequest`(product_title, category, desired_price) / `schema.AnalysisCreated`(analysis_id)
- [ ] 요청 시점의 사용자 활동동네(`User.region_id`)를 분석 기준 지역으로 사용
- [ ] 활동동네 미설정 사용자 → 400 (먼저 `PUT /auth/me/region` 필요 안내)
- 완료조건(DoD): 정상 요청 시 `Analysis` row 생성 및 id 반환, 활동동네 미설정 시 400

### TASK-02-02: 유사거래 조회 — `GET /api/v1/trades/analyses/{analysis_id}/similar` 🔒

- [ ] 같은 지역 + 같은 카테고리(+ 상품명 유사도) 기준으로 `Transaction` 필터링
- [ ] 유사도 판정은 1차로 `category` 일치 + `title` 부분 문자열/키워드 매칭 정도로 단순하게 시작 (임베딩 기반 유사도는 과설계 — 필요해지면 후순위로 도입)
- [ ] 존재하지 않는 `analysis_id` → 404, 본인 소유 아닌 analysis 조회 → 403
- 완료조건(DoD): 유사거래 리스트(가격, 등록시각, 거리 등)가 반환된다

### TASK-02-03: 적정가격 Range 산출 — `GET /api/v1/trades/analyses/{analysis_id}/price-range` 🔒

- [ ] TASK-02-02의 유사거래 집합을 기반으로 가격 범위 산출 (예: 사분위수 25%~75% 또는 표준편차 기반)
- [ ] PRD 예시: `52만원 ~ 57만원` 형태로 단일 값이 아닌 range 반환
- [ ] 표본이 3건 미만이면 "산정불가" 상태로 응답 (TASK-02-04의 거래빈도 등급과 기준 통일)
- 완료조건(DoD): 표본 충분 시 `{price_min, price_max}` 반환, 표본 부족 시 `status: "insufficient_data"` 형태로 명확히 구분해서 응답 (500 아님)

### TASK-02-04: 거래빈도 분석 — `GET /api/v1/trades/analyses/{analysis_id}/frequency` 🔒

- [ ] PRD 5절 기준 등급 산정 로직 구현:
  | 거래건수 | 등급 |
  | --- | --- |
  | 30건 이상 | 많음 |
  | 10~29건 | 보통 |
  | 3~9건 | 낮음 |
  | 3건 미만 | 산정불가 |
- [ ] 등급 산정 기준 기간(최근 N개월 등)을 명확히 정의하고 주석/문서로 남긴다 (PRD에 기간 명시 없음 — 임의 기본값 3개월로 잡고 조정 가능하게 상수화)
- 완료조건(DoD): 표본 건수별로 4개 등급이 표에 맞게 정확히 분류된다 (경계값 30/10/3 단위테스트 포함)

### TASK-02-05: 분석 근거 제공 — `GET /api/v1/trades/analyses/{analysis_id}/evidence` 🔒

- [ ] 채팅수·관심수·등록시각 기반 근거 데이터 구성 (PRD: "분석근거 제공")
- [ ] 근거로 사용된 유사거래 샘플(상위 N건)과 각 항목의 통계 요약 반환
- 완료조건(DoD): TASK-02-03/04 결과와 일관된 표본을 근거로 사용 (다른 표본 기준으로 따로 계산하지 않음 — 동일 쿼리 결과 재사용)

### TASK-02-06: 동네 인기상품 랭킹 — `GET /api/v1/trades/popular` 🔒

- 우선순위 미정 (API_DESIGN.md에도 "PRD 확인 필요"로 명시됨)
- [ ] 착수 전 PM/기획팀에 우선순위 확인 필요 — 확인 전까지 이 TASK는 보류
- 완료조건(DoD): 우선순위 확정 후 별도 논의

## 비고

- TR-07(예상 재판매가격, 3순위), TR-08(타 플랫폼 가격비교, 2순위)은 [09-backlog-2nd-3rd.md](09-backlog-2nd-3rd.md)에서 다룬다.
