# API 설계 문서 (EPIC 기반 라우터 분리)

> 근거: [기능명세서](https://claude.ai/code/artifact/b16c7759-ec69-4def-a82f-986859a38787) (PRD + 화면 흐름도 + `daangn_풀리오.csv` 분석 기반)
>
> 이 문서는 기능명세서의 EPIC 7개를 FastAPI 라우터 단위로 그대로 매핑하고, 명세서의 각 기능(ID) 1개당 엔드포인트 1개 이상을 배정한다. 아직 구현이 없는 초기 단계라 URI/스키마는 전부 **제안(draft)** 이며, 실제 구현하면서 조정해도 된다.

## 1. 컨벤션

- 전체 prefix: `/api/v1` (버전 프리픽스 없음 → 이번에 도입)
- EPIC 1개 = 라우터 1개 = 폴더 1개 (`router.py` / `service.py` / `schema.py` 3분리)
- `service.py` = "Context" — 해당 EPIC의 도메인 로직만 담당, DB/외부 API 호출은 여기서만
- `router.py`는 요청/응답 변환과 인증만 담당하고 로직은 service에 위임 (컨트롤러가 뚱뚱해지지 않게)
- 인증 필요 여부는 각 표의 🔒 열로 표시 (🔒 없으면 공개 API)
- 우선순위는 기능명세서를 그대로 따름 (1순위부터 구현)

## 1-1. DTO 공통 규칙

각 EPIC 폴더의 `schema.py`에 Pydantic DTO를 정의할 때 공통으로 따르는 규칙. 필드 목록 자체(뭘 요청/응답으로 주고받는지)는 각 `docs/issue/*.md`에 TASK별로 이미 나와있으니 그대로 옮기고, 여기 규칙은 "어떻게 짤지"만 다룬다.

- **네이밍**: 요청은 `XxxRequest`, 응답은 `XxxResponse` (생성 API는 `XxxCreated`도 허용 — 예: `AnalysisCreated`).
- **민감/내부 컬럼 금지**: `User.password_hash` 같은 DB 내부 컬럼은 어떤 응답 DTO에도 넣지 않는다. `docs/ERD.md`에서 컬럼을 확인하되, "그 컬럼이 있다"와 "API로 내보낸다"는 별개로 판단한다.
- **ORM 변환**: DB 모델을 그대로 응답으로 내보낼 때는 `model_config = {"from_attributes": True}`를 선언해 `Model.from_orm()` 없이 바로 반환할 수 있게 한다.
- **목록 응답은 페이지네이션 공통 포맷**: 매 EPIC마다 새로 만들지 않고 `app.core.pagination.Page[T]`(`items`, `total`)를 재사용한다.
- **"정상이지만 결과 없음/불가" 상태는 별도 필드로 명시**: 표본 부족, 분모 0 등은 500 에러가 아니라 응답 DTO 안에 `status`(예: `"insufficient_data"`) 필드나 `Optional` 값으로 명확히 구분한다. 억지로 값을 채우지 않는다.
- **enum은 앱 내부 Enum 재사용**: `role` 같은 필드는 `app/models`에 이미 있는 Enum(`UserRole` 등)을 그대로 타입으로 쓰고, EPIC마다 문자열 리터럴을 새로 정의하지 않는다.
- **날짜/시간은 UTC 그대로**: 타임존 변환은 프론트 책임, 서버는 `datetime`을 UTC 그대로 직렬화한다.

```
back/
└── app/
    ├── api/
    │   └── v1/
    │       ├── auth/           # 회원관리
    │       │   ├── router.py
    │       │   ├── service.py
    │       │   └── schema.py
    │       ├── admin/          # 어드민
    │       ├── local/          # 갖가지
    │       ├── trades/         # 중고거래
    │       ├── buyer_ai/       # 구매자AI
    │       ├── dream/          # 꿈가지
    │       └── local_share/    # 지역상생
    ├── core/                   # 공통 설정, 인증 Dependency, 예외 핸들러
    └── main.py
```

`main.py`에서 EPIC별 라우터를 그대로 include:

```python
from fastapi import FastAPI
from app.api.v1.auth.router import router as auth_router
from app.api.v1.admin.router import router as admin_router
from app.api.v1.local.router import router as local_router
from app.api.v1.trades.router import router as trades_router
from app.api.v1.buyer_ai.router import router as buyer_ai_router
from app.api.v1.dream.router import router as dream_router
from app.api.v1.local_share.router import router as local_share_router

app = FastAPI()

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(local_router)
app.include_router(trades_router)
app.include_router(buyer_ai_router)
app.include_router(dream_router)
app.include_router(local_share_router)
```

각 `router.py`는 자기 prefix/tag를 직접 들고 있는다 (아래 예시는 `trades`):

```python
# app/api/v1/trades/router.py
from fastapi import APIRouter, Depends
from app.api.v1.trades import schema, service

router = APIRouter(prefix="/api/v1/trades", tags=["중고거래"])


@router.post("/analyses", response_model=schema.AnalysisCreated)
def create_analysis(body: schema.AnalysisRequest):
    return service.create_analysis(body)


@router.get("/analyses/{analysis_id}/price-range", response_model=schema.PriceRange)
def get_price_range(analysis_id: int):
    return service.get_price_range(analysis_id)
```

---

## 2. EPIC → 라우터 매핑 요약

| EPIC | 라우터 폴더 | URI Prefix | 태그 |
| --- | --- | --- | --- |
| 회원관리 | `app/api/v1/auth/` | `/api/v1/auth` | `회원관리` |
| 어드민 | `app/api/v1/admin/` | `/api/v1/admin` | `어드민` |
| 갖가지 | `app/api/v1/local/` | `/api/v1/local` | `갖가지` |
| 중고거래 | `app/api/v1/trades/` | `/api/v1/trades` | `중고거래` |
| 구매자AI | `app/api/v1/buyer_ai/` | `/api/v1/buyer-ai` | `구매자AI` |
| 꿈가지 | `app/api/v1/dream/` | `/api/v1/dream` | `꿈가지` |
| 지역상생 | `app/api/v1/local_share/` | `/api/v1/local-share` | `지역상생` |

---

## 3. EPIC별 엔드포인트

### 회원관리 — `/api/v1/auth`

| 기능ID | Method | Endpoint | 설명 | 🔒 | 우선순위 |
| --- | --- | --- | --- | --- | --- |
| AUTH-01 | POST | `/api/v1/auth/signup` | 이메일 기반 회원가입 | | 1순위 |
| AUTH-01 | POST | `/api/v1/auth/login` | 로그인, JWT Access/Refresh 토큰 발급 | | 1순위 |
| AUTH-01 | POST | `/api/v1/auth/logout` | 로그아웃 (Refresh Token 폐기) | 🔒 | 1순위 |
| AUTH-01 | POST | `/api/v1/auth/refresh` | Refresh Token으로 Access Token 갱신 | | 1순위 |
| AUTH-02 | GET | `/api/v1/auth/me` | 내 정보 조회 (Role 포함) | 🔒 | 1순위 |
| AUTH-02 | PUT | `/api/v1/auth/me/region` | 활동동네·거래반경 설정 (User-지역 매핑) | 🔒 | 1순위 |
| AUTH-04 | GET | `/api/v1/auth/me/summary` | 마이페이지 요약 (활동동네·거래내역·포인트) | 🔒 | 1순위 |

> 사용자 Role 구분(권한관리)은 별도 엔드포인트가 아니라 `Depends(get_current_user)` / `Depends(require_admin)` 같은 인증 Dependency로 구현하고, 어드민 라우터 전체에 적용한다.

### 어드민 — `/api/v1/admin`

모든 엔드포인트에 `Depends(require_admin)` 적용 (= "관리자 API 보호").

| 기능ID | Method | Endpoint | 설명 | 🔒 | 우선순위 |
| --- | --- | --- | --- | --- | --- |
| AD-01 | GET | `/api/v1/admin/data-status` | 상품·지역별 수집 데이터 수, 오류 상태 대시보드 | 🔒 | 1순위 |
| AD-02 | GET | `/api/v1/admin/notices` | 수집된 공지 목록 조회 | 🔒 | 1순위 |
| AD-02 | PATCH | `/api/v1/admin/notices/{notice_id}/status` | 공지 상태 변경 | 🔒 | 1순위 |
| AD-02 | POST | `/api/v1/admin/notices/{notice_id}/alert` | 알림 생성 | 🔒 | 1순위 |
| AD-03 | GET | `/api/v1/admin/donations` | 기부 내역 목록 조회 | 🔒 | 2순위 |
| AD-03 | PATCH | `/api/v1/admin/donations/{donation_id}/review` | 기부 내역 검수 처리 | 🔒 | 2순위 |

### 갖가지 — `/api/v1/local`

| 기능ID | Method | Endpoint | 설명 | 🔒 | 우선순위 |
| --- | --- | --- | --- | --- | --- |
| LC-01 | POST | `/api/v1/local/collect` | 공사·단수·날씨 공공정보 수집 트리거 (배치/관리자용) | 🔒 | 1순위 |
| LC-02 | GET | `/api/v1/local/notices` | 내 활동동네 기준 공지 목록 (행정동 분류 적용) | 🔒 | 1순위 |
| LC-03 | — | (내부 로직) | 중복 공지 클러스터링/병합 — `/local/collect` 파이프라인 내부 처리, 별도 API 없음 | | — |
| LC-04 | — | (내부 로직) | 일시·위치·영향·행동요령 LLM 요약 — 수집 파이프라인 내부 처리, 결과는 `/local/notices`에 포함 | | — |
| LC-05 | GET | `/api/v1/local/notices/map` | 지도 마커용 공지 목록 (좌표 포함) | 🔒 | 1순위 |

> LC-05는 크롤링 데이터 검증 결과 좌표가 없다는 게 확인됐다 (기능명세서 참고) — 행정동-좌표 매핑 테이블을 먼저 만들어야 이 엔드포인트가 의미 있는 데이터를 낸다.

### 중고거래 — `/api/v1/trades`

| 기능ID | Method | Endpoint | 설명 | 🔒 | 우선순위 |
| --- | --- | --- | --- | --- | --- |
| TR-01 | POST | `/api/v1/trades/analyses` | 상품명/카테고리/희망가 입력 → 분석 요청 생성 | 🔒 | 1순위 |
| TR-02 | GET | `/api/v1/trades/analyses/{analysis_id}/similar` | 지역 내 유사거래 목록 | 🔒 | 1순위 |
| TR-03 | GET | `/api/v1/trades/analyses/{analysis_id}/price-range` | 적정가격 Range | 🔒 | 1순위 |
| TR-04 | GET | `/api/v1/trades/analyses/{analysis_id}/frequency` | 거래빈도 등급 (많음/보통/낮음/산정불가) | 🔒 | 1순위 |
| TR-05 | GET | `/api/v1/trades/analyses/{analysis_id}/evidence` | 분석 근거 (채팅수·관심수·등록시각 기반) | 🔒 | 1순위 |
| TR-06 | GET | `/api/v1/trades/popular` | 동네 인기상품 랭킹 (`region` 쿼리) | 🔒 | 미정 — PRD 확인 필요 |
| TR-07 | GET | `/api/v1/trades/analyses/{analysis_id}/resale-estimate` | 예상 재판매가격 | 🔒 | 3순위 |
| TR-08 | GET | `/api/v1/trades/analyses/{analysis_id}/platform-comparison` | 타 플랫폼(쿠팡 등) 가격 비교 | 🔒 | 2순위 |

### 구매자AI — `/api/v1/buyer-ai`

| 기능ID | Method | Endpoint | 설명 | 🔒 | 우선순위 |
| --- | --- | --- | --- | --- | --- |
| BA-01 | POST | `/api/v1/buyer-ai/price-evaluations` | 특정 매물가 적정성 평가 (적정/고가/저가) | 🔒 | 1순위 |
| BA-02 | POST | `/api/v1/buyer-ai/question-suggestions` | 상세설명 기반 구매 전 확인 질문 자동 생성 | 🔒 | 2순위 |

### 꿈가지 — `/api/v1/dream`

| 기능ID | Method | Endpoint | 설명 | 🔒 | 우선순위 |
| --- | --- | --- | --- | --- | --- |
| DR-01 | GET | `/api/v1/dream/points/me` | 내 포인트 잔액·적립 내역 조회 | 🔒 | 1순위 |
| DR-01 | POST | `/api/v1/dream/points/accrue` | 결제/거래 이벤트로 포인트 적립 (내부 호출) | 🔒 | 1순위 |
| DR-02 | GET | `/api/v1/dream/facilities` | 기부처(지원시설) 목록 조회 | | 1순위 |
| DR-02 | PUT | `/api/v1/dream/donation-settings` | 기부 비율/기부처 설정 | 🔒 | 1순위 |
| DR-03 | GET | `/api/v1/dream/donations/me` | 내 기부내역 조회 | 🔒 | 1순위 |

### 지역상생 — `/api/v1/local-share`

| 기능ID | Method | Endpoint | 설명 | 🔒 | 우선순위 |
| --- | --- | --- | --- | --- | --- |
| SH-01 | GET | `/api/v1/local-share/results` | 기부금 사용결과 공개 | | 1순위 |
| SH-02 | GET | `/api/v1/local-share/merchant-spends` | 지역 소상공인 집행내역 | | 1순위 |
| SH-03 | GET | `/api/v1/local-share/circulation-rate` | 지역 환류율 (집행금액 ÷ 전체 지원금 × 100) | | 1순위 |

---

## 4. 다음 단계

1. `app/core/` 에 인증 Dependency(`get_current_user`, `require_admin`) 먼저 구현 — 거의 모든 EPIC이 여기 의존한다.
2. 우선순위 1순위부터: `auth` → `trades`(TR-01~05) → `admin`(AD-01,02) → `local`(LC-01,02,05) → `dream` → `local_share` 순으로 구현 권장.
3. `TR-06`(동네 인기상품) 우선순위는 PRD MVP 범위표에 없어서 기능명세서에도 "확인 필요"로 남아있음 — 팀 확인 후 순서 조정.
4. Pydantic 스키마(`schema.py`)는 [기능명세서](https://claude.ai/code/artifact/b16c7759-ec69-4def-a82f-986859a38787)의 핵심 데이터 엔티티(User/Region/Product/Transaction/LocalNotice/Donation/Facility/MerchantSpend)를 기반으로 EPIC별로 파생해서 작성.
