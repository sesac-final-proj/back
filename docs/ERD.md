# ERD (DB 스키마 설계)

> 근거: [PRD.md](PRD.md) 7절 핵심 데이터, [API_DESIGN.md](API_DESIGN.md), `docs/issue/*.md`의 "데이터 모델" 절, `data/*.csv`(당근 중고거래 크롤링 원본), `carrot/mock_contract.py`(프론트 mock), 당근마켓 홈페이지(`daangn.com`) 동네생활 피드 구조
>
> DB는 PostgreSQL + SQLAlchemy(`app/core/db.py`) 기준. 아직 모델 코드가 없는 설계 단계라 컬럼/타입은 **제안(draft)**이며 Alembic 마이그레이션 작성 시 조정 가능.

## 0. 설계 결정 사항 (issue 문서의 미결 사항에 대한 답)

- **User 활동동네는 단일 FK로 간다.** `01-common-infra.md`가 "UserRegion 매핑 테이블로 분리할지 결정" 과제로 남겼는데, PRD MVP 문구("영등포-노원-송파 활동동네 및 거래반경 **설정**", `PUT /auth/me/region` — 단수 API)는 1인 1활동동네를 전제로 한다. 복수 동네가 실제로 필요해지면 `User.region_id`를 없애고 `UserRegion(user_id, region_id, radius_m, is_primary)` 매핑 테이블로 분리 — 지금 미리 만들지 않는다.
- **Region은 행정동 단독 테이블로 간다.** PRD가 말하는 "영등포/노원/송파"는 구(區) 단위지만 실제 서비스 단위는 행정동(예: 당산제1동)이라, 별도 `Gu` 테이블을 만드는 대신 `Region.gu_name` 컬럼 하나로 구 정보를 얹는다. 구가 3개뿐이라 정규화할 이유가 없다.
- **Transaction.region_id는 nullable.** CSV `지역` 값이 실제로 비어있는 행이 존재한다(원본 33건 중 다수가 빈 문자열). `LocalNotice.region_id`와 동일하게 "매칭 실패 시 NULL 허용" 패턴을 그대로 따른다.
- **Product 테이블을 mock과 통합했다.** PRD 데이터모델의 `Product`(분석 요청용: title/category/desired_price)와 `carrot/mock_contract.py`의 `ProductListItem`(실제 매물: trade_status/trade_type/favorite_count)은 "동네 중고 상품 1건"이라는 같은 개념이라 테이블을 나누지 않고 `trade_status`, `trade_type` 컬럼을 추가하는 쪽으로 합쳤다. 분석 전용 임시 상품이면 `trade_status`는 기본값(SALE)만 쓰고 무시하면 된다.
- **ChatRoom / ChatRoomParticipant는 실제로 착수했다 (갱신: 처음엔 참고용으로만 추가해뒀는데, "물건 등록/조회/채팅" 기본 마켓 기능 자체가 어떤 이슈 문서에도 없다는 게 뒤늦게 확인돼 `10-marketplace-core.md`로 새로 이슈를 만들고 구현함).** 여기 더해 실제 메시지 송수신을 위한 `ChatMessage`, 찜 기능을 위한 `ProductFavorite`도 이번에 추가했다 — 둘 다 원래 스키마엔 없던 테이블이라 사용자 승인 받고 진행했다 (2026-08-31). 동네생활(커뮤니티, `CommunityPost` 등)은 여전히 PRD/이슈 범위 밖으로 제외한다 — 이건 "당근 고도화니까 있어야 할 것 같다"는 개인 판단이었을 뿐 실제 요구사항이 아니라는 게 확인됐다.
- **`ChatMessage`를 `ChatRoom`과 별도 테이블로 뒀다.** `ChatRoom.last_message`/`last_message_at`는 목록 화면 미리보기용 캐시일 뿐, 방에 들어갔을 때 보이는 메시지 전체 내역은 별도 저장이 필요하다. 메시지 전송 시 `ChatRoom`의 캐시 컬럼을 같이 갱신하고, 상대방 `ChatRoomParticipant.unread_count`를 증가시킨다. 실시간 push(WebSocket 등)는 범위 밖 — REST 폴링 전제로 시작.
- **`ProductFavorite`는 `(user_id, product_id)` UNIQUE로 중복 찜을 막는다.** `Product.favorite_count`처럼 캐시 컬럼을 두지 않고 `COUNT(ProductFavorite) WHERE product_id = ...`로 그때그때 집계한다 (MVP 트래픽 규모에서 매번 집계해도 부담 없음 — `CommunityPost.emotion_count`와 반대로 여긴 아직 캐시할 근거가 없다).
- **AD-03(기부 검수) 관련 `Donation.review_status`는 뺐다.** `09-backlog-2nd-3rd.md`에 2순위로 명시된 기능이라 1순위 스키마에는 넣지 않는다. 착수 시점에 `ALTER TABLE donation ADD COLUMN review_status ...`로 추가.
- **동네생활(커뮤니티)은 당근 기본 기능이라 별도로 추가했다.** PRD/이슈 문서 어디에도 없지만, 이 플랫폼이 당근의 "고도화"인 이상 당근 홈(`daangn.com`) 자체가 제공하는 동네생활 게시판(글/댓글/공감)은 밑바탕 기능으로 필요하다는 게 확인됐다. `CommunityPost` / `Comment` / `PostReaction` 3테이블로 최소 구성 — 당근 홈 동네생활 피드가 실제로 쓰는 필드(제목/카테고리/썸네일/작성시각/공감수/댓글수)만 반영했고, 대댓글은 `Comment.parent_comment_id` 자기참조로 처리해서 별도 테이블을 만들지 않았다. 중고차/부동산/모임/알바 등 나머지 당근 버티컬은 PRD 범위 밖이라 넣지 않았다.
- **카카오/네이버 OAuth는 `SocialAccount` 테이블로 분리했다, `RefreshToken`을 재사용하지 않는다.** 이름은 같은 "access_token/refresh_token"이지만 성격이 다른 두 가지다 — `RefreshToken`(기존)은 *우리 서비스*가 로그인한 클라이언트에게 발급하는 JWT 재발급용 토큰이고, `SocialAccount.access_token`/`refresh_token`은 *카카오·네이버가* 우리 서버에 발급한, 그 사람 프로필을 다시 조회하거나 연동을 해제할 때 쓰는 토큰이다. 하나의 테이블에 억지로 합치면 의미가 섞여서 분리했다. 이메일 회원가입 없이 소셜 로그인만으로 가입하는 사용자를 지원해야 하므로 `User.password_hash`를 nullable로 바꿨다(단, 이메일 회원가입 유저는 필수 — 앱 레벨에서 `password_hash IS NOT NULL OR SocialAccount 존재` 정도로 검증).
- **`Facility` = 아동복지센터 또는 발달장애센터다 — `facility_type` 컬럼을 둔다.** (수정: 처음엔 기부처가 아동복지시설 하나뿐인 줄 알고 구분 컬럼을 뺐는데, "구별로 두 가지(아동복지센터/발달장애센터) 선정"이 확정되면서 실제로 값이 2종류가 됐다. 값이 하나뿐일 때 미리 넣는 건 과설계지만, 지금은 진짜 2종류가 있으니 enum 컬럼을 넣는 게 맞다.) `facility_type: "child_welfare" | "developmental_disability"` 로 구분한다. 구(Gu) 단위로 "각 타입당 1곳"을 고른다는 규칙은 큐레이션 정책이라 DB 제약(UNIQUE)으로 강제하지 않고 어드민 운영으로 관리 — 나중에 실제로 구별 2곳 제한이 깨지면 안 되는 요구사항이 되면 그때 `(gu_name, facility_type)` 부분 유니크를 검토한다.
- **포인트/기부금/집행금액이 같은 단위(원)로 이어지는 건 "1점=1원"이라는 별도 전제가 아니라 적립 공식 자체의 결과다.** `PointTransaction.amount`는 `06-dream.md` 적립 기준대로 `결제/거래금액 × 적립률`로 계산한다 — 일반결제 1%, 중고거래 0.1%(5,000원 이상 거래에만 적용). 이 적립률이 이미 원화 금액에 곱해지는 방식이라, 계산된 포인트 값 자체가 원화 단위로 나온다(예: 100,000원 결제 → 1,000포인트). 그 값이 `Donation.amount`(기부 포인트) → `MerchantSpend.amount`(실제 집행 금액, 원화)까지 그대로 이어져서 `07-local-share.md`의 지역 환류율 공식(`집행금액 ÷ 전체 지원금 × 100`)이 별도 전환 없이 성립한다. 세 컬럼 모두 int(원 단위)로 둔 이유가 여기 있다 — 포인트 가치를 원화와 분리하는 정책(예: 포인트별 별도 환율)이 실제로 생기면 그때 전환 컬럼/로직을 추가한다.
- **꿈가지 대시보드의 "모금 진행률"과 지역상생 SH-03의 "지역 환류율"은 공식이 다른 별개 지표다 — 이름이 겹치지 않게 문서상 분리했다.** 꿈가지 쪽(이번에 새로 정의된 `현재 모금액 ÷ 반기별 목표금액 × 100`)은 `FundraisingGoal` 테이블을 새로 추가해서 계산하고, SH-03(`집행금액 ÷ 전체 지원금 × 100`, `MerchantSpend` 기반)은 그대로 둔다. 사용자 확인: 둘 다 유지하기로 결정.
- **`FundraisingGoal`(반기별 목표 모금액)을 `Facility`에 딸린 테이블로 추가했다.** "기부 현황(목표 모금액 %화)" 대시보드가 시설별·반기별 목표 대비 진행률을 보여줘야 해서 필요하다. "현재 모금액"은 별도 컬럼으로 캐싱하지 않고 `SUM(Donation.amount) WHERE facility_id = ... AND created_at BETWEEN period_start AND period_end`로 그때그때 계산한다 — MVP 트래픽 규모에서 매번 집계해도 부담 없고, `CommunityPost.emotion_count`처럼 캐시 컬럼을 미리 둘 근거가 아직 없다 (조회가 느려지면 그때 캐시 컬럼 추가). "기부 참여 횟수"도 같은 이유로 `COUNT(Donation)` 집계로 처리하고 별도 카운터 컬럼을 두지 않는다.
- **`Facility.lat`/`lng`를 추가했다.** "지도에서 기부금액 현황을 확인"하려면 지도 핀 좌표가 필요하다. `LocalNotice`와 동일한 패턴으로 시설 자체 좌표는 nullable로 두고, 없으면 `Region.lat/lng`(소재 행정동 대표 좌표)를 fallback으로 쓴다.
- **"나의 기부액" → "우리 동네 모금가지" 명칭 변경은 스키마에 영향 없다.** `Donation` 데이터 자체는 그대로고, API가 사용자 개인 기부내역 대신 "그 사용자의 활동동네(`User.region_id`) 기준 지역 집계"를 보여주는 것으로 바뀌는 것 — `Donation.facility_id → Facility.region_id → Region.gu_name`로 이미 집계 가능해서 테이블 추가가 필요 없다.

---

## 1. ERD

```mermaid
erDiagram
    Region ||--o{ User : "활동동네"
    Region ||--o{ Product : "지역"
    Region ||--o{ Transaction : "지역(매칭)"
    Region ||--o{ Analysis : "분석 기준지역"
    Region ||--o{ LocalNotice : "지역(매칭)"
    Region ||--o{ Facility : "소재지역"
    Region ||--o{ MerchantSpend : "지역"

    User ||--o{ RefreshToken : "발급"
    User ||--o{ SocialAccount : "소셜연동"
    User ||--o{ Product : "created_by"
    User ||--o{ Analysis : "requested_by"
    User ||--o| PointAccount : "보유"
    User ||--o{ PointTransaction : "적립/사용"
    User ||--o| DonationSetting : "설정"
    User ||--o{ Donation : "기부"
    User ||--o{ Alert : "생성(admin)"
    User ||--o{ ChatRoomParticipant : "참여"
    User ||--o{ CommunityPost : "작성"
    User ||--o{ Comment : "작성"
    User ||--o{ PostReaction : "공감"

    Region ||--o{ CommunityPost : "지역"

    Product ||--o{ Analysis : "분석 대상"
    Product ||--o{ ChatRoom : "거래 채팅"
    Product ||--o{ ProductFavorite : "찜"
    User ||--o{ ProductFavorite : "찜한 사람"

    Analysis ||--|| AnalysisResult : "산출"

    LocalNotice ||--o{ Alert : "알림 트리거"

    Facility ||--o{ DonationSetting : "선택된 기부처"
    Facility ||--o{ Donation : "기부처"
    Facility ||--o{ MerchantSpend : "집행 주체(nullable)"
    Facility ||--o{ FundraisingGoal : "반기별 목표"

    PointTransaction ||--o{ Donation : "적립 계기(nullable)"

    ChatRoom ||--o{ ChatRoomParticipant : "참여자"
    ChatRoom ||--o{ ChatMessage : "메시지"
    User ||--o{ ChatMessage : "발신"

    CommunityPost ||--o{ Comment : "댓글"
    CommunityPost ||--o{ PostReaction : "공감"
    Comment ||--o{ Comment : "대댓글(parent)"

    Region {
        int id PK
        string dong_code UK
        string dong_name
        string gu_name
        float lat
        float lng
        datetime created_at
    }

    User {
        int id PK
        string email UK
        string password_hash "nullable, 소셜 로그인 전용 유저는 없음"
        string nickname
        string role "user | admin"
        int region_id FK "nullable"
        int radius_m "nullable"
        datetime created_at
    }

    RefreshToken {
        int id PK
        int user_id FK
        string token UK
        bool revoked
        datetime expires_at
        datetime created_at
    }

    SocialAccount {
        int id PK
        int user_id FK
        string provider "kakao | naver"
        string provider_user_id "UK with provider"
        string access_token "provider가 발급, 암호화 저장 권장"
        string refresh_token "nullable, provider가 발급"
        datetime token_expires_at "nullable"
        datetime connected_at
    }

    Product {
        int id PK
        string title
        string category "상세카테고리"
        string search_keyword "nullable"
        int desired_price "nullable"
        int region_id FK
        int created_by FK "nullable, User"
        string trade_status "SALE|RESERVED|SOLD"
        string trade_type "SALE|FREE"
        datetime created_at
    }

    ProductFavorite {
        int id PK
        int user_id FK
        int product_id FK
        datetime created_at
    }

    Transaction {
        int id PK
        string product_title
        string search_keyword "nullable"
        string category
        string detail_category "nullable"
        int price "nullable, 나눔 등"
        int region_id FK "nullable"
        string status "원문 상태 그대로: 거래완료/나눔완료 등"
        string trade_place "nullable"
        text description "nullable"
        string seller_nickname "nullable"
        float seller_manner_temp "nullable"
        int chat_count
        int interest_count
        int view_count
        date listed_at
        datetime traded_at "nullable"
        datetime collected_at
    }

    Analysis {
        int id PK
        int product_id FK
        int region_id FK
        int requested_by FK "User"
        string status "pending | done"
        datetime created_at
    }

    AnalysisResult {
        int id PK
        int analysis_id FK UK
        int price_min "nullable"
        int price_max "nullable"
        string frequency_grade "많음|보통|낮음|산정불가"
        int sample_count
        json evidence_json
        datetime computed_at
    }

    LocalNotice {
        int id PK
        string source "공사|단수|날씨"
        int region_id FK "nullable"
        string title
        text raw_content
        json summary_json "일시/위치/영향/행동요령"
        float lat "nullable"
        float lng "nullable"
        string status "draft|published|hidden"
        string dedup_group_id "nullable"
        datetime collected_at
    }

    Alert {
        int id PK
        int notice_id FK
        int created_by FK "User(admin)"
        datetime created_at
    }

    CollectionError {
        int id PK
        string source
        text message
        datetime occurred_at
    }

    PointAccount {
        int user_id PK, FK
        int balance
    }

    PointTransaction {
        int id PK
        int user_id FK
        int amount "원 단위, 결제/거래금액 × 적립률로 계산"
        string source "general_payment(가지페이 결제, 1%) | trade(중고거래, 0.1%·5,000원↑)"
        int related_id "nullable"
        datetime created_at
    }

    Facility {
        int id PK
        string name "예: OO아동복지센터, OO발달장애복지관"
        string facility_type "child_welfare | developmental_disability"
        int region_id FK
        float lat "nullable, 없으면 Region 대표좌표 fallback"
        float lng "nullable"
        text description "nullable"
    }

    FundraisingGoal {
        int id PK
        int facility_id FK
        date period_start "반기 시작일"
        date period_end "반기 종료일"
        int target_amount "원 단위, 반기 목표 모금액"
        datetime created_at
    }

    DonationSetting {
        int user_id PK, FK
        int donation_rate "0~100"
        int facility_id FK "nullable"
    }

    Donation {
        int id PK
        int user_id FK
        int facility_id FK "선택한 Facility"
        int point_transaction_id FK "nullable"
        int amount "원 단위, 기부한 포인트 금액"
        datetime created_at
    }

    MerchantSpend {
        int id PK
        int facility_id FK "nullable, 집행한 Facility"
        int region_id FK
        string merchant_name
        int amount "원 단위"
        date spent_at
        text description "nullable"
    }

    ChatRoom {
        int id PK
        string type "TRADE|COMMUNITY|GROUP|SYSTEM"
        string title
        int product_id FK "nullable, TRADE 타입만"
        string last_message "nullable"
        datetime last_message_at "nullable"
        bool verified
        datetime created_at
    }

    ChatRoomParticipant {
        int id PK
        int chat_room_id FK
        int user_id FK
        int unread_count
        datetime joined_at
    }

    ChatMessage {
        int id PK
        int chat_room_id FK
        int sender_id FK "User"
        text content
        datetime created_at
    }

    CommunityPost {
        int id PK
        int user_id FK
        int region_id FK
        string category "일반|반려동물|고민상담 등"
        string title
        text content
        string thumbnail_url "nullable"
        int view_count
        int emotion_count "공감수 캐시"
        int comment_count "댓글수 캐시"
        datetime created_at
    }

    Comment {
        int id PK
        int post_id FK "CommunityPost"
        int user_id FK
        int parent_comment_id FK "nullable, 대댓글"
        text content
        datetime created_at
    }

    PostReaction {
        int id PK
        int post_id FK "CommunityPost"
        int user_id FK
        datetime created_at
    }
```

---

## 2. 테이블별 컬럼 요약

### 공통/회원관리

| Region | User | RefreshToken | SocialAccount |
| --- | --- | --- | --- |
| id PK | id PK | id PK | id PK |
| dong_code UK | email UK | user_id FK | user_id FK |
| dong_name | password_hash (nullable) | token UK | provider ("kakao\|naver") |
| gu_name | nickname | revoked | provider_user_id (UK with provider) |
| lat | role ("user\|admin") | expires_at | access_token |
| lng | region_id FK (nullable) | created_at | refresh_token (nullable) |
| created_at | radius_m (nullable) | | token_expires_at (nullable) |
| | created_at | | connected_at |

### 중고거래

| Product | ProductFavorite | Transaction | Analysis | AnalysisResult |
| --- | --- | --- | --- | --- |
| id PK | id PK | id PK | id PK | id PK |
| title | user_id FK | product_title | product_id FK | analysis_id FK UK |
| category | product_id FK | search_keyword (nullable) | region_id FK | price_min (nullable) |
| search_keyword (nullable) | created_at | category | requested_by FK (User) | price_max (nullable) |
| desired_price (nullable) | (user_id, product_id) UK | detail_category (nullable) | status ("pending\|done") | frequency_grade |
| region_id FK | | price (nullable) | created_at | sample_count |
| created_by FK (nullable) | | region_id FK (nullable) | | evidence_json |
| trade_status | | status | | computed_at |
| trade_type | | trade_place (nullable) | | |
| created_at | | description (nullable) | | |
| | | seller_nickname (nullable) | | |
| | | seller_manner_temp (nullable) | | |
| | | chat_count / interest_count / view_count | | |
| | | listed_at / traded_at (nullable) / collected_at | | |

### 갖가지 / 어드민

| LocalNotice | Alert | CollectionError |
| --- | --- | --- |
| id PK | id PK | id PK |
| source ("공사\|단수\|날씨") | notice_id FK | source |
| region_id FK (nullable) | created_by FK (User, admin) | message |
| title | created_at | occurred_at |
| raw_content | | |
| summary_json | | |
| lat / lng (nullable) | | |
| status ("draft\|published\|hidden") | | |
| dedup_group_id (nullable) | | |
| collected_at | | |

### 꿈가지

| PointAccount | PointTransaction | Facility | FundraisingGoal | DonationSetting | Donation |
| --- | --- | --- | --- | --- | --- |
| user_id PK, FK | id PK | id PK | id PK | user_id PK, FK | id PK |
| balance | user_id FK | name | facility_id FK | donation_rate (0~100) | user_id FK |
| | amount | facility_type ("child_welfare\|developmental_disability") | period_start | facility_id FK (nullable) | facility_id FK |
| | source ("general_payment\|trade") | region_id FK | period_end | | point_transaction_id FK (nullable) |
| | related_id (nullable) | lat / lng (nullable) | target_amount | | amount |
| | created_at | description (nullable) | created_at | | created_at |

### 지역상생

| MerchantSpend |
| --- |
| id PK |
| facility_id FK (nullable) |
| region_id FK |
| merchant_name |
| amount |
| spent_at |
| description (nullable) |

### 동네생활 (당근 기본 기능)

| CommunityPost | Comment | PostReaction |
| --- | --- | --- |
| id PK | id PK | id PK |
| user_id FK | post_id FK | post_id FK |
| region_id FK | user_id FK | user_id FK |
| category | parent_comment_id FK (nullable) | created_at |
| title | content | |
| content | created_at | |
| thumbnail_url (nullable) | | |
| view_count | | |
| emotion_count (캐시) | | |
| comment_count (캐시) | | |
| created_at | | |

### 채팅 (기본 마켓)

| ChatRoom | ChatRoomParticipant | ChatMessage |
| --- | --- | --- |
| id PK | id PK | id PK |
| type ("TRADE\|COMMUNITY\|GROUP\|SYSTEM") | chat_room_id FK | chat_room_id FK |
| title | user_id FK | sender_id FK (User) |
| product_id FK (nullable) | unread_count | content |
| last_message (nullable) | joined_at | created_at |
| last_message_at (nullable) | | |
| verified | | |
| created_at | | |

---

## 3. 테이블별 비고 (EPIC 매핑)

| 테이블 | 소속 EPIC | 관련 이슈 |
| --- | --- | --- |
| `Region`, `User`, `RefreshToken`, `SocialAccount` | 공통/회원관리 | [01-common-infra.md](issue/01-common-infra.md), [02-auth.md](issue/02-auth.md) |
| `Product` | 중고거래(가격분석), 중고거래(기본 마켓) | [03-trades.md](issue/03-trades.md), [10-marketplace-core.md](issue/10-marketplace-core.md) |
| `Transaction`, `Analysis`, `AnalysisResult` | 중고거래(가격분석) | [03-trades.md](issue/03-trades.md) |
| `ProductFavorite`, `ChatRoom`, `ChatRoomParticipant`, `ChatMessage` | 중고거래(기본 마켓) | [10-marketplace-core.md](issue/10-marketplace-core.md) |
| `LocalNotice`, `Alert`, `CollectionError` | 갖가지 / 어드민 | [05-local.md](issue/05-local.md), [04-admin.md](issue/04-admin.md) |
| `PointAccount`, `PointTransaction`, `Facility`, `FundraisingGoal`, `DonationSetting`, `Donation` | 꿈가지 | [06-dream.md](issue/06-dream.md) |
| `MerchantSpend` | 지역상생 | [07-local-share.md](issue/07-local-share.md) |
| `CommunityPost`, `Comment`, `PostReaction` | (범위 제외) | PRD/이슈에 없음 — MVP 범위에서 제외하기로 확정 (2026-08-31) |

- 구매자AI([08-buyer-ai.md](issue/08-buyer-ai.md))는 전용 테이블이 없다 — `AnalysisResult`(가격 Range/빈도)를 그대로 재사용하는 규칙 기반 판정이라 스키마가 필요 없다는 게 이슈 문서 방침.
- `PostReaction`은 `(post_id, user_id)` 유니크 제약으로 중복 공감을 막는다 (한 게시글에 한 유저가 공감 1번).
- `CommunityPost.emotion_count` / `comment_count`는 `PostReaction`/`Comment` 실제 건수를 매번 집계하지 않기 위한 캐시 컬럼 — insert/delete 시 갱신(트리거 대신 서비스 레이어에서 증감 처리, 데이터 늘어나서 실제로 느려지면 그때 트리거 도입).
- `SocialAccount`는 `(provider, provider_user_id)` 유니크 — 같은 카카오 계정으로 두 User가 생기는 것을 막는다. `(user_id, provider)`도 유니크로 둬서 한 유저가 같은 provider를 두 번 연동하지 못하게 한다 (재연동 시 기존 row UPDATE).
- 꿈가지 → 지역상생 데이터 흐름: `PointTransaction`(가지페이 결제/중고거래로 적립) → `Donation`(적립 시점에 `DonationSetting.donation_rate`만큼 자동으로 `Facility`에 기부, `06-dream.md` TASK-05-05) → `MerchantSpend`(그 `Facility`가 지역 소상공인에게 집행) → `07-local-share.md`의 지역 환류율(`MerchantSpend.amount 합계 ÷ Donation.amount 합계 × 100`)로 이어진다. `Facility` 하나가 `Donation`(받는 쪽)과 `MerchantSpend`(쓰는 쪽) 양쪽에 다 걸리는 게 이 흐름의 핵심이라 두 테이블 모두 `facility_id`로 같은 시설을 가리키게 설계했다.
- 꿈가지 대시보드(기부 시설·기부 현황·기부 참여 횟수)는 별도 API 흐름: 시설별 `FundraisingGoal`(반기 목표) 대비 `SUM(Donation.amount)`(현재 모금액)로 진행률을 내고, `COUNT(Donation)`으로 참여 횟수를 낸다. 지도 화면은 `Facility.lat/lng`(nullable) → 없으면 `Region.lat/lng`로 핀을 찍는다. 이 지표는 위 `MerchantSpend` 기반 지역상생 환류율과 이름만 "환류율"로 겹쳐 보일 뿐 완전히 별개다 — 헷갈리지 않게 API/화면에서는 "모금 진행률"로 부르는 걸 권장.

---

## 4. CSV(`data/*.csv`) → `Transaction` 컬럼 매핑

당근 크롤링 데이터(`daangn_브레짜 분유포트_영등포구_당산제1동.csv`, 33건)를 `TASK-02-00`(거래 원천 데이터 적재)에서 그대로 이 매핑으로 적재하면 된다.

| CSV 컬럼 | Transaction 컬럼 | 비고 |
| --- | --- | --- |
| 카테고리 | `category` | 검색 대분류 (예: "분유포트") |
| 검색어 | `search_keyword` | |
| 제목 | `product_title` | |
| 상태 | `status` | 원문 값 그대로 저장 (`거래완료`/`나눔완료`, 판매중 매물도 향후 값 추가될 수 있음) |
| 가격 | `price` | `"310,000원"` → 콤마·"원" 제거 후 int 변환, 나눔 등 빈 값은 NULL |
| 지역 | `region_id` | `Region.dong_name`과 매칭. **원본에 빈 문자열 행 존재** → 매칭 안 되면 NULL |
| 등록시각 | `listed_at` | |
| 채팅수 | `chat_count` | |
| 관심수 | `interest_count` | |
| 조회수 | `view_count` | |
| 매너온도 | `seller_manner_temp` | 빈 문자열(`""`)은 NULL, `"45.5℃"` → `℃` 제거 후 float |
| 판매자닉네임 | `seller_nickname` | |
| 상세카테고리 | `detail_category` | 빈 값 존재(NULL 허용) |
| 거래희망장소 | `trade_place` | |
| 상세설명 | `description` | |
| (크롤링 시각, CSV엔 없음) | `collected_at` | 적재 스크립트 실행 시각으로 채움 |

`traded_at`은 CSV에 없다(등록시각만 존재) — `상태=거래완료/나눔완료`인 원본은 실거래 완료건이므로, 정확한 완료 시각을 모르면 `listed_at`으로 대체하거나 NULL로 두고 추후 필드가 생기면 채운다.

---

## 5. 당근 홈(daangn.com) 동네생활 피드 → `CommunityPost` 필드 매핑

당근 홈페이지 동네생활 섹션(`homeCommunityArticles`)이 실제로 내려주는 필드 기준.

| 당근 홈 필드 | CommunityPost 컬럼 | 비고 |
| --- | --- | --- |
| `title` | `title` | |
| `categoryName` | `category` | "일반", "반려동물" 등 |
| `thumbnailUrl` | `thumbnail_url` | 썸네일 없는 글도 있음(nullable) |
| `publishedAt` | `created_at` | |
| `emotionCount` | `emotion_count` | 공감수 |
| `commentCount` | `comment_count` | 댓글수 |
| (당근 홈엔 없음, 이 서비스 전용) | `region_id`, `user_id`, `view_count`, `content` | 활동동네 필터·작성자·본문은 서비스에서 직접 관리 |

---

## 6. 카카오/네이버 OAuth 로그인 흐름과 테이블

`POST /api/v1/auth/oauth/{provider}/callback` (provider = kakao | naver) 하나로 두 provider를 같이 처리한다 — provider별 라우터를 따로 만들 이유가 없다 (redirect URI만 provider별로 다르면 됨).

1. 프론트가 카카오/네이버 인가 코드(`code`)를 이 엔드포인트로 전달
2. 서버가 provider 토큰 엔드포인트에 `code`를 교환 → provider의 `access_token`/`refresh_token` 수신
3. provider 프로필 API로 `provider_user_id`(카카오는 `id`, 네이버는 `response.id`) 조회
4. `SocialAccount(provider, provider_user_id)`로 기존 연동 여부 조회
   - 있으면: 해당 `User`로 로그인 처리, `SocialAccount`의 토큰 3종(`access_token`/`refresh_token`/`token_expires_at`) 갱신
   - 없으면: `User` 신규 생성(이메일은 provider가 주면 채우고 없으면 nullable 허용 확인 필요 — 카카오는 비즈앱 등록 안 하면 이메일 미제공 케이스가 흔함) + `SocialAccount` row 생성
5. 이후는 이메일 로그인과 동일 — 우리 서비스 `RefreshToken`을 발급하고 JWT Access Token 반환 (`docs/issue/02-auth.md` TASK-01-02와 동일 응답 스키마 `TokenResponse` 재사용, provider 분기는 이 콜백 엔드포인트 내부에서 끝남)

**주의**: `SocialAccount.access_token`/`refresh_token`은 사용자 개인정보에 준하는 민감정보라 평문 컬럼에 그대로 넣기보다 애플리케이션 레벨 암호화(예: KMS/Fernet)를 권장 — 지금 스키마엔 컬럼만 정의해두고, 암호화 방식은 실제 구현 시점(TASK-01-08 정도로 신설)에 결정한다.
