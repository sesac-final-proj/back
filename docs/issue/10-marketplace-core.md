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

- [x] `schema.ProductCreateRequest`(title, category, desired_price, trade_type) / `schema.ProductCreated`(id)
- [x] 로그인 사용자의 활동동네(`User.region_id`)를 상품 지역으로 사용, 활동동네 미설정 시 400
- [x] `trade_status` 기본값은 `SALE`
- 완료조건(DoD): 정상 등록 시 201 + `Product` row 생성, 활동동네 미설정 400, 잘못된 `trade_type` 422

### TASK-08-02: 상품 목록 조회 — `GET /api/v1/trades/products`

- [x] `schema.ProductListItem`은 `carrot/mock_contract.py`의 `ProductListItem` 필드 그대로 맞춘다: `id`, `title`, `neighborhood_name`, `created_at`, `price`, `trade_status`, `trade_type`, `chat_count`, `favorite_count`
  - `neighborhood_name`은 `Region.dong_name`에서, `chat_count`/`favorite_count`는 우선 0 또는 관련 카운트 테이블이 생기기 전까지 스텁 처리 가능 (관심수 저장 테이블은 이 TASK 범위 밖 — 필요해지면 별도 TASK)
- [x] 지역/카테고리/거래상태(`trade_status`) 필터 + `app.core.pagination.Page` 사용
- 완료조건(DoD): 필터 조합 정상 동작, 결과 없어도 200 + 빈 배열

### TASK-08-03: 상품 상세 조회 — `GET /api/v1/trades/products/{product_id}`

- [x] 상세설명 등 목록에 없는 필드 포함 반환
- [x] 존재하지 않는 `product_id` → 404
- 완료조건(DoD): 정상 조회 200, 없는 id 404

### TASK-08-04: 상품 거래상태 변경 — `PATCH /api/v1/trades/products/{product_id}/status` 🔒

- [x] `schema.ProductStatusUpdateRequest`(trade_status)
- [x] 본인(`created_by`)이 아닌 사용자가 변경 시도 → 403
- [x] 존재하지 않는 `product_id` → 404
- 완료조건(DoD): 정상 변경 200, 타인 소유 403, 없는 id 404, 잘못된 상태값 422

### TASK-08-05: 채팅방 생성 — `POST /api/v1/chats` 🔒

- [x] `schema.ChatRoomCreateRequest`(type, product_id nullable) / `schema.ChatRoomResponse`(`carrot/mock_contract.py`의 `ChatRoom` 필드 그대로: id, type, title, last_message, last_message_at, unread_count, verified)
- [x] `type="TRADE"`인데 `product_id`가 없으면 422
- [x] 채팅방 생성 시 요청자를 `ChatRoomParticipant`로 자동 추가
- 완료조건(DoD): TRADE 타입 정상 생성 200, product_id 없이 TRADE 생성 시도 422

### TASK-08-06: 내 채팅방 목록 — `GET /api/v1/chats` 🔒

- [x] 로그인 사용자가 `ChatRoomParticipant`로 속한 채팅방만 반환, 최근 메시지순 정렬
- 완료조건(DoD): 참여 중인 방만 반환, 참여 없으면 빈 배열

### TASK-08-07: 상품 정보 수정 — `PATCH /api/v1/trades/products/{product_id}` 🔒

- [x] `schema.ProductUpdateRequest`(title, category, desired_price, search_keyword — 전부 optional, 부분 수정)
- [x] 본인(`created_by`)이 아닌 사용자가 수정 시도 → 403
- [x] 존재하지 않는 `product_id` → 404
- 완료조건(DoD): 정상 수정 200, 타인 소유 403, 없는 id 404

### TASK-08-08: 상품 검색 — `GET /api/v1/trades/products`에 키워드 파라미터 추가

- [x] `q`(검색어) 쿼리 파라미터 추가, `title` 또는 `search_keyword`에 부분일치(`ILIKE`)
- 완료조건(DoD): 검색어 포함 상품만 반환, 검색어 없으면 기존과 동일하게 전체 반환

### TASK-08-09: 찜(관심상품) — `POST/DELETE /api/v1/trades/products/{product_id}/favorite` 🔒, `GET /api/v1/trades/products/favorites` 🔒

- [x] **DB 스키마 변경 필요** — `docs/ERD.md`에 없던 테이블. 착수 전 사용자 승인 필요 (제안: `product_favorites`(id, user_id, product_id, created_at), `(user_id, product_id)` UNIQUE)
- [x] `ProductListItem.favorite_count`를 이 테이블 기준 실제 카운트로 교체 (지금은 0 고정)
- 완료조건(DoD): 찜 추가/취소 정상 동작, 중복 찜 방지, 내 찜 목록 조회

### TASK-08-10: 채팅 메시지 송수신 — `POST /api/v1/chats/{chat_room_id}/messages` 🔒, `GET /api/v1/chats/{chat_room_id}/messages` 🔒

- [x] **DB 스키마 변경 필요** — `docs/ERD.md`에 없던 테이블. 착수 전 사용자 승인 필요 (제안: `chat_messages`(id, chat_room_id, sender_id, content, created_at))
- [x] 메시지 전송 시 `ChatRoom.last_message`/`last_message_at` 갱신, 상대방 `ChatRoomParticipant.unread_count` 증가
- [x] 메시지 조회 시 본인 `ChatRoomParticipant.unread_count`는 0으로 초기화
- [x] 실시간 push(WebSocket 등)는 이 TASK 범위 밖 — REST로 보내고 받는 것까지만 (폴링 전제)
- 완료조건(DoD): 메시지 전송 후 목록에 반영, 참여자 아닌 사용자가 조회 시도 시 403

### TASK-08-11: 내 상품 목록 — `GET /api/v1/trades/products/mine` 🔒

- [x] 로그인 사용자가 `created_by`인 상품만 반환 (판매완료 포함 전체 상태), 기존 `list_products` 로직을 `created_by` 필터로 재사용 (중복 구현 안 함)
- [x] `/products/{product_id}`보다 먼저 라우터에 등록 (경로 세그먼트 수가 같아 순서 중요 — `/products/favorites`와 동일한 이유)
- 완료조건(DoD): 본인이 등록한 상품만 반환, 없으면 빈 배열

### TASK-08-12: 상품 삭제 — `DELETE /api/v1/trades/products/{product_id}` 🔒

- [x] 본인(`created_by`) 아니면 403, 없는 `product_id`면 404
- [x] 삭제 시 연관 데이터 정리: `ProductFavorite`는 같이 삭제(의미 없어지므로), 해당 상품을 참조하던 `ChatRoom.product_id`는 NULL로 변경(채팅 기록 자체는 보존 — `ChatRoom.product_id`가 원래 nullable로 설계돼 있어 그대로 활용)
- 완료조건(DoD): 정상 삭제 204, 타인 소유 403, 없는 id 404, 삭제 후 목록/상세 조회 시 404

## 비고

- **범위를 "중고거래 자체" 기능으로만 한정한다.** 동네생활(커뮤니티 게시판, `CommunityPost`/`Comment`/`PostReaction`)은 PRD·이슈 문서 어디에도 명시된 요구사항이 아니라서 이 이슈에서 다루지 않는다 (MVP 3주 일정상 핵심 3축에 집중, 필요해지면 별도 백로그). 실제 배포된 프론트(`ongaji.site`)에 "커뮤니티"/"중고차"/"부동산"/"기타 서비스" 메뉴가 보이지만, 확인 결과 버튼만 만들어둔 미구현 상태 — 백엔드도 대응하지 않는다.
- 실시간 알림/푸시는 TASK-08-10에서도 범위 밖 — REST 폴링 전제로 시작.
