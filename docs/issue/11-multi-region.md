# 내 동네 다중 설정 (multi-region)

> 브랜치: `feat/multi-region`
> 우선순위: 2순위 (기존 활동동네 기능의 확장 — 프론트 UI 작업과 병행)
> API prefix: `/api/v1/auth` (태그: `회원관리`)
> 관련 문서: [02-auth.md](02-auth.md) TASK-01-06, [ERD.md](../ERD.md) "0. 설계 결정 사항" 1번째 항목, [API_DESIGN.md](../API_DESIGN.md)

## 개요

지금은 유저 1명이 활동동네를 딱 1개(`User.region_id` 단일 FK)만 가질 수 있다. 실제 당근마켓처럼 **최대 2개**까지 등록하고, 그중 하나를 "대표 동네"로 지정할 수 있게 확장한다.

이건 처음부터 예정돼 있던 확장이다 — `ERD.md`에 이렇게 적혀있다:

> User 활동동네는 단일 FK로 간다. ... **복수 동네가 실제로 필요해지면 `User.region_id`를 없애고 `UserRegion(user_id, region_id, radius_m, is_primary)` 매핑 테이블로 분리** — 지금 미리 만들지 않는다.

지금이 그 시점이다. 프론트에서 아래 UX로 화면을 이미 만들고 있다(`feat/neighborhood-list` 브랜치):

- "내 동네 설정" 바텀시트: 등록된 동네를 최대 2개까지 행으로 보여줌. 각 행에 라디오(대표 동네 지정)와 X(삭제) 버튼. 동네가 1개뿐이면 X 없음(마지막 하나는 못 지움).
- 동네가 1개뿐일 때만 "+ 동네 추가" 버튼 노출.
- 동네 검색 화면에서 고르면: 슬롯이 비어있으면 새로 추가, 이미 2개면 "대표 동네 교체" 흐름으로 이어짐(기존 TASK-01-06 `PUT /me/region`과 동일한 자리 이동 개념).

## 선행 조건

- [02-auth.md](02-auth.md) TASK-01-06 완료 상태 (`User.region_id`/`radius_m`, `PUT /api/v1/auth/me/region` 기존 구현)
- [10-marketplace-core.md](10-marketplace-core.md) 완료 (`Product.region_id` 등 region 기반 필터링이 이미 동작 중)

## 데이터 모델

### 새 테이블: `user_regions`

```text
user_regions
  id            PK
  user_id       FK -> users.id, NOT NULL
  region_id     FK -> regions.id, NOT NULL
  radius_m      INT, NOT NULL (기존 User.radius_m과 동일 개념 — 동네별로 다르게 가질 수 있음)
  is_primary    BOOLEAN, NOT NULL, default false
  created_at    TIMESTAMPTZ, server_default now()

  UNIQUE (user_id, region_id)   -- 같은 동네 중복 등록 방지
```

정합성 규칙(DB 제약이 아니라 서비스 레이어에서 보장 — 아래 "정합성 규칙" 절 참고):

- 유저 1명당 최대 2행, 최소 1행(0개가 되는 상태는 금지 — 마지막 동네는 삭제 불가)
- `is_primary = true`인 행은 유저당 항상 정확히 1개

### `User.region_id` / `User.radius_m`은 그대로 둔다 (제거하지 않음)

ERD 원안은 "`User.region_id`를 없애고" 라고 되어 있지만, 실제로 이 두 컬럼을 읽는 곳이 이미 여러 군데다:

- `trades/service.py`의 `create_product` — 글쓰기 시 `region_id=user.region_id`로 상품에 지역을 박음
- `trades/service.py`의 분석 요청 생성(`region_id=user.region_id`)
- `auth/service.py`의 `get_me_summary`

이 컬럼들을 아예 없애면 위 소비처를 전부 "primary user_region 조인"으로 고쳐야 해서 이번 이슈 범위가 커진다. 대신 **`User.region_id`/`radius_m`을 "현재 primary `user_regions` 행의 캐시"로 유지**한다 — `is_primary`가 바뀔 때마다 서비스 레이어에서 같이 갱신. 기존 소비처는 코드를 한 줄도 안 고쳐도 계속 "지금 대표 동네" 기준으로 정확히 동작한다.

(이 판단이 마음에 안 들면 — 예: "캐시 두 군데 동기화는 버그 소지"라고 보면 — `trades/service.py` 소비처들을 primary 조인으로 바꾸고 `User.region_id`/`radius_m` 컬럼을 걷어내는 쪽으로 가도 된다. 그 경우 위에 나열한 소비처 전부가 이번 이슈 스코프에 들어간다.)

### 마이그레이션

1. `user_regions` 테이블 생성 (Alembic)
2. 데이터 백필: 기존 `users.region_id`가 NULL이 아닌 유저는 `user_regions`에 `is_primary=true`인 행 1개씩 생성 (`radius_m`도 기존 값 그대로 복사)
3. `users.region_id`/`radius_m` 컬럼은 삭제하지 않음 (위 이유)

## API

### TASK-11-01: 내 동네 목록 조회 — `GET /api/v1/auth/me/regions` 🔒

- [ ] 응답: `{ items: [{ region_id, dong_name, gu_name, radius_m, is_primary }] }`, primary가 배열 앞에 오도록 정렬
- 완료조건(DoD): 동네 1개 등록 상태에서 배열 길이 1, 2개 등록 상태에서 길이 2 + primary 하나만 true

### TASK-11-02: 동네 추가 — `POST /api/v1/auth/me/regions` 🔒

- [ ] `schema.UserRegionCreateRequest`(region_id 또는 dong_code, radius_m, is_primary: bool = false)
- [ ] 이미 2개 등록된 상태에서 호출 → 409 Conflict ("이미 동네를 2개 등록했어요. 하나를 삭제한 뒤 추가해주세요." 같은 메시지) — 프론트는 이 케이스를 "빈 슬롯 없음"으로 미리 막아야 하지만 서버도 반드시 막는다
- [ ] 이미 등록된 `region_id` 재등록 시도 → 409 Conflict
- [ ] 존재하지 않는 `region_id`/`dong_code` → 404
- [ ] `is_primary=true`로 요청하거나, **유저의 첫 동네 등록**이면 무조건 `is_primary=true`로 저장하고 기존 primary는 자동으로 false로 내림 (동시에 `User.region_id`/`radius_m` 캐시 갱신)
  - 프론트 쪽 의도: "새로 검색해서 추가하는 동네는 방금 둘러보려는 곳이니 바로 대표로" — 그래서 검색 후 추가는 기본적으로 `is_primary=true`로 보낼 걸로 예상
- 완료조건(DoD): 정상 추가 201, 2개 초과 409, 중복 동네 409, 없는 지역 404

### TASK-11-03: 대표 동네 전환 — `PATCH /api/v1/auth/me/regions/{region_id}` 🔒

- [ ] `schema.UserRegionUpdateRequest`(is_primary: true 고정 — 지금은 이 용도로만 씀, radius_m도 같이 바꿀 수 있게 optional로 열어둠)
- [ ] 대상 `region_id`가 이 유저의 등록 동네가 아니면 404
- [ ] `is_primary=true` 처리 시 기존 primary였던 다른 행을 자동으로 false로 (한 트랜잭션 안에서, 항상 정확히 1개만 true 보장)
- [ ] `User.region_id`/`radius_m` 캐시 갱신
- 완료조건(DoD): 전환 후 `GET /me/regions`에서 지정한 동네만 `is_primary: true`

### TASK-11-04: 동네 삭제 — `DELETE /api/v1/auth/me/regions/{region_id}` 🔒

- [ ] 유저에게 남은 동네가 1개뿐이면 → 400 ("최소 1개의 동네는 있어야 해요") — 프론트가 이 경우 X 버튼 자체를 숨기지만 서버도 막는다
- [ ] 대상 `region_id`가 이 유저의 등록 동네가 아니면 404
- [ ] **삭제 대상이 primary였고 다른 동네가 남아있으면, 남은 동네를 자동으로 primary로 승격** (`User.region_id`/`radius_m` 캐시도 그 동네 기준으로 갱신)
- 완료조건(DoD): 2개 중 primary 삭제 → 남은 1개가 자동으로 primary가 됨, 1개만 있을 때 삭제 시도 → 400

### TASK-11-05: 기존 `PUT /api/v1/auth/me/region` 처리 방침

- [ ] 이 엔드포인트는 유지한다 (하위 호환 — 다른 화면/과거 클라이언트가 쓸 수도 있음)
- [ ] 동작을 "primary 동네를 이 값으로 바꾼다"로 재정의: 내부적으로 TASK-11-02(첫 등록이거나 새 지역이면 추가) 또는 TASK-11-03(이미 등록된 지역이면 전환) 로직을 재사용
- 완료조건(DoD): 기존처럼 호출해도 여전히 200, 결과가 `user_regions`에도 반영됨

## 정합성 규칙 (서비스 레이어에서 보장)

DB 제약(예: partial unique index on `is_primary`)으로 강제해도 되고 서비스 레이어 트랜잭션으로만 보장해도 된다 — 유저당 최대 2행이라 트래픽 부담이 없으니 과설계(파셜 유니크 인덱스 등) 없이 서비스 레이어 검증만으로 충분하다고 본다. 아래 불변식만 항상 지키면 됨:

1. 유저 1명당 `user_regions` 행 수는 1 또는 2
2. `is_primary=true`인 행은 유저당 정확히 1개
3. `User.region_id`/`radius_m`은 항상 그 유저의 현재 primary `user_regions` 행과 같은 값

## MeResponse 영향

- [ ] `MeResponse.region`/`radius_m`은 그대로 유지 (= primary 동네, 캐시에서 그대로 읽음 — 스키마 변경 없음)
- [ ] 프론트가 동네 목록 전체가 필요하면 `GET /me/regions`를 별도 호출 (온보딩/설정 화면에서만 필요, 홈 피드 등 나머지 화면은 기존 `MeResponse.region` 하나로 충분)

## 테스트

- [ ] 동네 1개 → 2개 추가 → 목록 조회 순서(primary 먼저)
- [ ] 3번째 추가 시도 → 409
- [ ] 같은 동네 중복 추가 → 409
- [ ] 대표 전환 → 기존 대표가 false로 내려가는지
- [ ] 대표 삭제 → 남은 동네가 자동 승격되는지, `User.region_id` 캐시도 같이 바뀌는지
- [ ] 마지막 1개 삭제 시도 → 400
- [ ] 기존 `PUT /me/region` 호출 결과가 `user_regions`/`User.region_id` 양쪽에 반영되는지 (하위 호환 회귀 테스트)
- [ ] 기존 `test_marketplace_core.py`/`test_product_images.py` 등 `user.region_id`를 직접 쓰는 자가점검 테스트가 캐시 컬럼 방식 그대로 통과하는지 (컬럼을 안 지웠으니 회귀 없어야 정상)

## 비고

- 프론트는 `feat/neighborhood-list` 브랜치에서 이 API를 소비할 예정. 응답 필드명(`region_id`/`dong_name`/`gu_name`/`radius_m`/`is_primary`)은 기존 `RegionSummary`(`dong_name`/`gu_name`) 표기와 맞춰뒀으니 그대로 따라가면 프론트 쪽 매핑 코드가 최소화된다.
- "최대 2개"는 지금 하드코딩 상수(`MAX_USER_REGIONS = 2`)로 두고, 나중에 정책이 바뀌면 그 값만 조정 — 지금 설정 테이블 등으로 빼는 건 과설계.
