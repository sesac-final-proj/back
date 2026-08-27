# 구매자AI (buyer_ai)

> 브랜치: `feat/buyer-ai`
> 우선순위: BA-01 1순위 / BA-02 2순위
> API prefix: `/api/v1/buyer-ai` (태그: `구매자AI`)
> 관련 문서: [API_DESIGN.md](../API_DESIGN.md) "구매자AI" 절

## 개요

구매자가 특정 매물 가격이 적정한지 평가받고, 구매 전 확인할 질문을 AI로 생성받는다.

## 선행 조건

- [03-trades.md](03-trades.md) TASK-02-03(적정가격 Range), TASK-02-04(거래빈도) — 가격 평가 로직이 이 데이터를 재사용

## Task 목록

### TASK-07-01: 가격 적정성 평가 — `POST /api/v1/buyer-ai/price-evaluations` 🔒

- [ ] `schema.PriceEvaluationRequest`(product_title, category, listed_price, region) / `schema.PriceEvaluationResponse`(verdict: 적정/고가/저가, price_range, diff_percent)
- [ ] 신규 AI 모델을 새로 만들지 않는다 — [03-trades.md](03-trades.md)의 적정가격 Range 산출 로직(TASK-02-03)을 그대로 호출해서 `listed_price`가 range 안/밖 어디에 위치하는지로 판정 (규칙 기반, 별도 ML 모델 불필요)
- [ ] 표본 부족(산정불가) 지역/카테고리는 "평가불가" 응답으로 명확히 구분
- 완료조건(DoD): range 내부/상단 초과/하단 미만/산정불가 4가지 케이스 단위테스트

### TASK-07-02: 구매 전 확인 질문 생성 — `POST /api/v1/buyer-ai/question-suggestions` 🔒

- 우선순위: 2순위 — TASK-07-01 완료 후 착수
- [ ] `schema.QuestionSuggestionRequest`(product_description) / `schema.QuestionSuggestionResponse`(questions: string[])
- [ ] 상품 상세설명 텍스트를 LLM에 전달해 확인 질문 N개 생성 (프롬프트에 카테고리별 체크리스트 예시 포함해 품질 확보 — 전자기기는 하자/구성품, 가구는 상태/직거래 여부 등)
- [ ] LLM 실패 시 빈 배열이 아니라 최소한의 기본 질문 세트(fallback)로 응답 (완전 실패 시에도 사용자에게 빈 화면 노출 안 함)
- 완료조건(DoD): 정상 케이스 + LLM 실패 fallback 케이스 모두 테스트
