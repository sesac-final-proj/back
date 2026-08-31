-- ==========================================================================
-- 가지마켓 DB 스키마 (PostgreSQL DDL)
--
-- 근거: docs/ERD.md (mermaid erDiagram) 그대로 옮긴 것. ERD를 고치면 이 파일도 같이 고친다.
-- 실제 서비스 마이그레이션은 Alembic이 관리한다(01-common-infra.md TASK-00-02) —
-- 이 파일은 그 첫 리비전을 만들 때 참고할 "정답지"이자, 로컬에서 빠르게
--   psql -U <user> -d <db> -f data/schema.sql
-- 로 스키마를 그대로 띄워볼 때 쓰는 용도다.
--
-- 컨벤션
--   - 테이블명: snake_case 복수형 (users, regions, ...) — `user`가 예약어 근처라 헷갈리는 것 방지
--   - PK: SERIAL(4바이트) — ERD에 전부 `int id`로 표기했으므로 BIGSERIAL 대신 SERIAL
--   - enum: 네이티브 ENUM 타입 대신 VARCHAR + CHECK — 값 추가할 때 ALTER TYPE 없이 CHECK만 바꾸면 됨
--   - 시각: TIMESTAMPTZ (타임존 포함) / 날짜만 필요하면 DATE
--   - 금액: INTEGER, 원 단위 정수 (docs/ERD.md 0절 "포인트=원" 설계 결정 참고)
--   - JSON: JSONB
-- ==========================================================================

-- --------------------------------------------------------------------------
-- 0. 공통/회원관리
-- --------------------------------------------------------------------------

CREATE TABLE regions (
    id          SERIAL PRIMARY KEY,
    dong_code   VARCHAR(20) NOT NULL UNIQUE,
    dong_name   VARCHAR(50) NOT NULL,
    gu_name     VARCHAR(50) NOT NULL,
    lat         DOUBLE PRECISION,
    lng         DOUBLE PRECISION,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE users (
    id             SERIAL PRIMARY KEY,
    email          VARCHAR(255) NOT NULL UNIQUE,
    password_hash  VARCHAR(255),                      -- nullable: 소셜 로그인 전용 유저는 없음
    nickname       VARCHAR(50) NOT NULL,
    role           VARCHAR(20) NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
    region_id      INTEGER REFERENCES regions(id) ON DELETE SET NULL,
    radius_m       INTEGER,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_users_region_id ON users(region_id);

CREATE TABLE refresh_tokens (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token       VARCHAR(512) NOT NULL UNIQUE,
    revoked     BOOLEAN NOT NULL DEFAULT false,
    expires_at  TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);

-- 카카오/네이버 OAuth. access_token/refresh_token은 provider가 발급한 토큰 —
-- 우리 서비스가 클라이언트에 주는 refresh_tokens와는 별개 (docs/ERD.md 0절 참고).
CREATE TABLE social_accounts (
    id                SERIAL PRIMARY KEY,
    user_id           INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider          VARCHAR(20) NOT NULL CHECK (provider IN ('kakao', 'naver')),
    provider_user_id  VARCHAR(100) NOT NULL,
    access_token      VARCHAR(1024) NOT NULL,          -- 애플리케이션 레벨 암호화 권장 (평문 저장 금지)
    refresh_token     VARCHAR(1024),
    token_expires_at  TIMESTAMPTZ,
    connected_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (provider, provider_user_id),
    UNIQUE (user_id, provider)
);

-- --------------------------------------------------------------------------
-- 1. 중고거래
-- --------------------------------------------------------------------------

CREATE TABLE products (
    id             SERIAL PRIMARY KEY,
    title          VARCHAR(200) NOT NULL,
    category       VARCHAR(50) NOT NULL,
    search_keyword VARCHAR(100),
    desired_price  INTEGER,
    region_id      INTEGER NOT NULL REFERENCES regions(id) ON DELETE RESTRICT,
    created_by     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    trade_status   VARCHAR(20) NOT NULL DEFAULT 'SALE' CHECK (trade_status IN ('SALE', 'RESERVED', 'SOLD')),
    trade_type     VARCHAR(20) NOT NULL DEFAULT 'SALE' CHECK (trade_type IN ('SALE', 'FREE')),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_products_region_id ON products(region_id);
CREATE INDEX idx_products_created_by ON products(created_by);

-- 당근 크롤링 원천 데이터. CSV → 컬럼 매핑은 docs/ERD.md 4절 참고.
CREATE TABLE transactions (
    id                  SERIAL PRIMARY KEY,
    product_title       VARCHAR(200) NOT NULL,
    search_keyword      VARCHAR(100),
    category            VARCHAR(50) NOT NULL,
    detail_category     VARCHAR(50),
    price               INTEGER,                       -- nullable: 나눔 등
    region_id           INTEGER REFERENCES regions(id) ON DELETE SET NULL,
    status              VARCHAR(30) NOT NULL,           -- 원문 그대로: 거래완료/나눔완료 등
    trade_place         VARCHAR(200),
    description         TEXT,
    seller_nickname     VARCHAR(100),
    seller_manner_temp  NUMERIC(4, 1),
    chat_count          INTEGER NOT NULL DEFAULT 0,
    interest_count      INTEGER NOT NULL DEFAULT 0,
    view_count          INTEGER NOT NULL DEFAULT 0,
    listed_at           DATE NOT NULL,
    traded_at           TIMESTAMPTZ,
    collected_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_transactions_region_category ON transactions(region_id, category);

CREATE TABLE analyses (
    id             SERIAL PRIMARY KEY,
    product_id     INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    region_id      INTEGER NOT NULL REFERENCES regions(id) ON DELETE RESTRICT,
    requested_by   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status         VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'done')),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_analyses_requested_by ON analyses(requested_by);

CREATE TABLE analysis_results (
    id               SERIAL PRIMARY KEY,
    analysis_id      INTEGER NOT NULL UNIQUE REFERENCES analyses(id) ON DELETE CASCADE,
    price_min        INTEGER,
    price_max        INTEGER,
    frequency_grade  VARCHAR(10) NOT NULL CHECK (frequency_grade IN ('많음', '보통', '낮음', '산정불가')),
    sample_count     INTEGER NOT NULL DEFAULT 0,
    evidence_json    JSONB,
    computed_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- --------------------------------------------------------------------------
-- 2. 갖가지 / 어드민
-- --------------------------------------------------------------------------

CREATE TABLE local_notices (
    id               SERIAL PRIMARY KEY,
    source           VARCHAR(20) NOT NULL CHECK (source IN ('공사', '단수', '날씨')),
    region_id        INTEGER REFERENCES regions(id) ON DELETE SET NULL,
    title            VARCHAR(200) NOT NULL,
    raw_content      TEXT NOT NULL,
    summary_json     JSONB,                            -- 일시/위치/영향/행동요령
    lat              DOUBLE PRECISION,
    lng              DOUBLE PRECISION,
    status           VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'hidden')),
    dedup_group_id   VARCHAR(64),
    collected_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_local_notices_region_status ON local_notices(region_id, status);

CREATE TABLE alerts (
    id          SERIAL PRIMARY KEY,
    notice_id   INTEGER NOT NULL REFERENCES local_notices(id) ON DELETE CASCADE,
    created_by  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE collection_errors (
    id           SERIAL PRIMARY KEY,
    source       VARCHAR(20) NOT NULL,
    message      TEXT NOT NULL,
    occurred_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- --------------------------------------------------------------------------
-- 3. 꿈가지
-- --------------------------------------------------------------------------

CREATE TABLE point_accounts (
    user_id  INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    balance  INTEGER NOT NULL DEFAULT 0
);

-- amount = 결제/거래금액 × 적립률(일반결제 1% / 중고거래 0.1%, 5,000원 이상)로 계산된
-- 원 단위 값. docs/ERD.md 0절 참고 — "1점=1원"이라는 별도 전제가 아니라 이 계산식의 결과.
CREATE TABLE point_transactions (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount      INTEGER NOT NULL,
    source      VARCHAR(20) NOT NULL CHECK (source IN ('general_payment', 'trade')),
    related_id  INTEGER,                                -- 결제/거래 원본 id (다른 테이블 참조 아님, 느슨한 연결)
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_point_transactions_user_id ON point_transactions(user_id);

-- 기부처: 구(Gu) 별로 아동복지센터/발달장애센터 각 1곳 (큐레이션, DB 제약 아님)
CREATE TABLE facilities (
    id             SERIAL PRIMARY KEY,
    name           VARCHAR(100) NOT NULL,
    facility_type  VARCHAR(30) NOT NULL CHECK (facility_type IN ('child_welfare', 'developmental_disability')),
    region_id      INTEGER NOT NULL REFERENCES regions(id) ON DELETE RESTRICT,
    lat            DOUBLE PRECISION,                     -- nullable: 없으면 regions.lat/lng를 fallback으로 사용
    lng            DOUBLE PRECISION,
    description    TEXT
);
CREATE INDEX idx_facilities_region_id ON facilities(region_id);

-- 시설별 반기 목표 모금액. "현재 모금액"은 컬럼으로 안 두고
-- SUM(donations.amount) WHERE facility_id = ... AND created_at BETWEEN period_start AND period_end 로 계산.
CREATE TABLE fundraising_goals (
    id             SERIAL PRIMARY KEY,
    facility_id    INTEGER NOT NULL REFERENCES facilities(id) ON DELETE CASCADE,
    period_start   DATE NOT NULL,
    period_end     DATE NOT NULL,
    target_amount  INTEGER NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (facility_id, period_start),
    CHECK (period_end > period_start)
);

CREATE TABLE donation_settings (
    user_id         INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    donation_rate   INTEGER NOT NULL CHECK (donation_rate BETWEEN 0 AND 100),
    facility_id     INTEGER REFERENCES facilities(id) ON DELETE SET NULL
);

CREATE TABLE donations (
    id                     SERIAL PRIMARY KEY,
    user_id                INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    facility_id            INTEGER NOT NULL REFERENCES facilities(id) ON DELETE RESTRICT,
    point_transaction_id   INTEGER REFERENCES point_transactions(id) ON DELETE SET NULL,
    amount                 INTEGER NOT NULL,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_donations_facility_created_at ON donations(facility_id, created_at);
CREATE INDEX idx_donations_user_id ON donations(user_id);

-- --------------------------------------------------------------------------
-- 4. 지역상생
-- --------------------------------------------------------------------------

CREATE TABLE merchant_spends (
    id             SERIAL PRIMARY KEY,
    facility_id    INTEGER REFERENCES facilities(id) ON DELETE SET NULL,
    region_id      INTEGER NOT NULL REFERENCES regions(id) ON DELETE RESTRICT,
    merchant_name  VARCHAR(100) NOT NULL,
    amount         INTEGER NOT NULL,
    spent_at       DATE NOT NULL,
    description    TEXT
);
CREATE INDEX idx_merchant_spends_facility_id ON merchant_spends(facility_id);
CREATE INDEX idx_merchant_spends_region_id ON merchant_spends(region_id);

-- --------------------------------------------------------------------------
-- 5. 동네생활 (당근 기본 기능)
-- --------------------------------------------------------------------------

CREATE TABLE community_posts (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    region_id       INTEGER NOT NULL REFERENCES regions(id) ON DELETE RESTRICT,
    category        VARCHAR(30) NOT NULL,
    title           VARCHAR(200) NOT NULL,
    content         TEXT NOT NULL,
    thumbnail_url   VARCHAR(500),
    view_count      INTEGER NOT NULL DEFAULT 0,
    emotion_count   INTEGER NOT NULL DEFAULT 0,          -- post_reactions 캐시, 서비스 레이어에서 증감
    comment_count   INTEGER NOT NULL DEFAULT 0,          -- comments 캐시, 서비스 레이어에서 증감
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_community_posts_region_created_at ON community_posts(region_id, created_at);

CREATE TABLE comments (
    id                  SERIAL PRIMARY KEY,
    post_id             INTEGER NOT NULL REFERENCES community_posts(id) ON DELETE CASCADE,
    user_id             INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    parent_comment_id   INTEGER REFERENCES comments(id) ON DELETE CASCADE,
    content             TEXT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_comments_post_id ON comments(post_id);

CREATE TABLE post_reactions (
    id          SERIAL PRIMARY KEY,
    post_id     INTEGER NOT NULL REFERENCES community_posts(id) ON DELETE CASCADE,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (post_id, user_id)                            -- 한 게시글에 한 유저 공감 1번
);

-- --------------------------------------------------------------------------
-- 6. 참고용 (미착수 — carrot/mock_contract.py 기반 제안, 실제 이슈 TASK 없음)
-- --------------------------------------------------------------------------

CREATE TABLE chat_rooms (
    id                SERIAL PRIMARY KEY,
    type              VARCHAR(20) NOT NULL CHECK (type IN ('TRADE', 'COMMUNITY', 'GROUP', 'SYSTEM')),
    title             VARCHAR(200) NOT NULL,
    product_id        INTEGER REFERENCES products(id) ON DELETE SET NULL,  -- TRADE 타입만 사용
    last_message      VARCHAR(500),
    last_message_at   TIMESTAMPTZ,
    verified          BOOLEAN NOT NULL DEFAULT false,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE chat_room_participants (
    id             SERIAL PRIMARY KEY,
    chat_room_id   INTEGER NOT NULL REFERENCES chat_rooms(id) ON DELETE CASCADE,
    user_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    unread_count   INTEGER NOT NULL DEFAULT 0,
    joined_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (chat_room_id, user_id)
);
