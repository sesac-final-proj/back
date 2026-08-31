# 기본 마켓 기능 (marketplace-core)

> 브랜치: `feat/marketplace-core`
> 우선순위: 실질적 선행 (PRD TR-00 "기존 당근거래 플랫폼 기능" — [03-trades.md](03-trades.md)의 가격분석은 이 기능이 있든 없든 텍스트 입력만으로 동작하지만, 실제 서비스로서는 상품 등록/조회/채팅이 먼저 있어야 한다. 착수 전 우선순위 재확인 권장)
> API prefix: `/api/v1/trades`(상품), `/api/v1/chats`(채팅) — 태그: `중고거래`, `채팅`
> 관련 문서: [docs/ERD.md](../ERD.md) `Product`/`ChatRoom`/`ChatRoomParticipant`, [carrot/mock_contract.py](../../carrot/mock_contract.py)(프론트가 이미 이 모양으로 mock 중 — 실제 연동 시 이 필드 그대로 맞춰야 함)

## 개요

지금까지의 이슈 문서(`02-auth.md`~`09-backlog-2nd-3rd.md`)는 전부 "분석/생활정보/기부" 기능만 다루고, 실제 "물건을 등록하고 팔고 채팅하는" 기본 마켓 기능(당근의 기존 핵심 기능)은 어디에도 없었다. `docs/ERD.md`엔 `Product`, `ChatRoom`, `ChatRoomParticipant` 테이블이 이미 정의돼 있고 DB에도 생성돼 있으며, 프론트는 `carrot/mock_contract.py`로 이미 이 기능을 mock 상태로 구현해뒀다 — 이 문서는 그 mock을 실제 API로 대체하기 위한 이슈다.

## 선행 조건

- [01-common-infra.md](01-common-infra.md) 완료 (`Region`, 인증 Dependency)
- [02-auth.md](02-auth.md) 완료 (상품 등록·채팅은 로그인 필요)

## 데이터 모델

- `Product`(`docs/ERD.md` 기준): `id`, `title`, `category`, `search_keyword`(nullable), `desired_price`(nullable), `region_id`, `created_by`(nullable), `trade_status`(`SALE`/`RESERVED`/`SOLD`), `trade_type`(`SALE`/`FREE`), `created_at`
- `ChatRoom`: `id`, `type`(`TRADE`/`COMMUNITY`/`GROUP`/`SYSTEM`), `title`, `product_id`(nullable, TRADE만), `last_message`(nullable), `last_message_at`(nullable), `verified`, `created_at`
- `ChatRoomParticipant`: `id`, `chat_room_id`, `user_id`, `unread_count`, `joined_at`
- 테이블은 이미 DB에 있으므로 마이그레이션은 `alembic stamp`로 기록만 맞추면 된다 (`upgrade`로 새로 생성 시도하지 않는다).

## Task 목록

### TASK-08-01: 상품 등록 — `POST /api/v1/trades/products` 🔒

- [ ] `schema.ProductCreateRequest`(title, category, desired_price, trade_type) / `schema.ProductCreated`(id)
- [ ] 로그인 사용자의 활동동네(`User.region_id`)를 상품 지역으로 사용, 활동동네 미설정 시 400
- [ ] `trade_status` 기본값은 `SALE`
- 완료조건(DoD): 정상 등록 시 201 + `Product` row 생성, 활동동네 미설정 400, 잘못된 `trade_type` 422

### TASK-08-02: 상품 목록 조회 — `GET /api/v1/trades/products`

- [ ] `schema.ProductListItem`은 `carrot/mock_contract.py`의 `ProductListItem` 필드 그대로 맞춘다: `id`, `title`, `neighborhood_name`, `created_at`, `price`, `trade_status`, `trade_type`, `chat_count`, `favorite_count`
  - `neighborhood_name`은 `Region.dong_name`에서, `chat_count`/`favorite_count`는 우선 0 또는 관련 카운트 테이블이 생기기 전까지 스텁 처리 가능 (관심수 저장 테이블은 이 TASK 범위 밖 — 필요해지면 별도 TASK)
- [ ] 지역/카테고리/거래상태(`trade_status`) 필터 + `app.core.pagination.Page` 사용
- 완료조건(DoD): 필터 조합 정상 동작, 결과 없어도 200 + 빈 배열

### TASK-08-03: 상품 상세 조회 — `GET /api/v1/trades/products/{product_id}`

- [ ] 상세설명 등 목록에 없는 필드 포함 반환
- [ ] 존재하지 않는 `product_id` → 404
- 완료조건(DoD): 정상 조회 200, 없는 id 404

### TASK-08-04: 상품 거래상태 변경 — `PATCH /api/v1/trades/products/{product_id}/status` 🔒

- [ ] `schema.ProductStatusUpdateRequest`(trade_status)
- [ ] 본인(`created_by`)이 아닌 사용자가 변경 시도 → 403
- [ ] 존재하지 않는 `product_id` → 404
- 완료조건(DoD): 정상 변경 200, 타인 소유 403, 없는 id 404, 잘못된 상태값 422

### TASK-08-05: 채팅방 생성 — `POST /api/v1/chats` 🔒

- [ ] `schema.ChatRoomCreateRequest`(type, product_id nullable) / `schema.ChatRoomResponse`(`carrot/mock_contract.py`의 `ChatRoom` 필드 그대로: id, type, title, last_message, last_message_at, unread_count, verified)
- [ ] `type="TRADE"`인데 `product_id`가 없으면 422
- [ ] 채팅방 생성 시 요청자를 `ChatRoomParticipant`로 자동 추가
- 완료조건(DoD): TRADE 타입 정상 생성 200, product_id 없이 TRADE 생성 시도 422

### TASK-08-06: 내 채팅방 목록 — `GET /api/v1/chats` 🔒

- [ ] 로그인 사용자가 `ChatRoomParticipant`로 속한 채팅방만 반환, 최근 메시지순 정렬
- 완료조건(DoD): 참여 중인 방만 반환, 참여 없으면 빈 배열

## 비고

- **실시간 메시지 송수신(WebSocket 등)은 이 이슈 범위 밖.** `last_message`/`last_message_at` 갱신과 실제 메시지 내역 저장/조회는 별도 이슈로 분리 — 지금은 채팅방 껍데기(생성/목록)까지만.
- `favorite_count`(관심수) 저장이 필요해지면 별도 테이블/컬럼 추가를 이 TASK가 아니라 후속 TASK로 분리한다 (지금은 없는 값이라 0 또는 nullable로 시작).
