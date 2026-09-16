# 갖가지 (local)

> 브랜치: `feat/local`
> 우선순위: 1순위
> API prefix: `/api/v1/local` (태그: `갖가지`)
> 관련 문서: [API_DESIGN.md](../API_DESIGN.md) "갖가지" 절, PRD 5절 "갖가지" Flow

## 개요

공사·단수·날씨 등 지역 생활정보를 수집해 AI로 요약하고 지도에서 제공. Flow: `공공정보 수집 → 행정동 분류 → 중복공지 제거 → LLM 요약 → 지도 표시`

## 선행 조건

- [01-common-infra.md](01-common-infra.md) 완료 (`Region` 테이블)
- 초기 데이터 소스(공사/단수/날씨) API 키·엔드포인트 확보 필요 — 없으면 TASK-04-01 착수 전 확인

## 데이터 모델

- `LocalNotice`: `id`, `source`(공사/단수/날씨), `region_id`, `title`, `raw_content`, `summary`(일시/위치/영향/행동요령 — LLM 요약 결과), `lat`, `lng`(nullable), `status`(draft/published/hidden), `dedup_group_id`(nullable), `collected_at`

## Task 목록

### TASK-04-01: 공공정보 수집 파이프라인 — `POST /api/v1/local/collect` 🔒(admin/배치)

- [ ] 공사/단수/날씨 3개 소스 각각의 수집 함수 작성 (소스별 어댑터 패턴까진 필요 없음 — 소스 3개면 함수 3개로 충분, 소스가 계속 늘어날 때만 추상화 고려)
- [ ] 수집 결과를 `LocalNotice`에 `raw_content`로 우선 적재 (요약 전 상태)
- [ ] 수집 실패 시 [04-admin.md](04-admin.md) TASK-03-01의 오류 로그(`CollectionError`)에 기록
- [ ] 이 엔드포인트는 관리자 수동 트리거용. 주기 자동 실행(cron)은 배포 환경 설정 시점에 별도로 (APScheduler 등 도입은 실제 주기 실행 필요해지는 시점에 결정 — 지금은 수동 트리거 API로 충분)
- 완료조건(DoD): 호출 시 3개 소스에서 원문 데이터가 수집되어 `LocalNotice`에 적재된다

### TASK-04-02: 행정동 분류 (내부 로직, LC-03 연계)

- [ ] 수집된 원문에서 지역명을 추출해 `Region`과 매칭 (주소 문자열 매칭 — 형태소분석기 등 무거운 NLP 도입 전에 키워드 매칭으로 우선 시도)
- [ ] 매칭 실패(지역 특정 불가) 건은 `region_id NULL`로 남기고 관리자 화면에서 확인 가능하게
- 완료조건(DoD): 수집 데이터의 N% 이상이 region_id 매칭됨 (초기 목표치는 실측 후 결정, 0건 매칭 방지가 최우선)

### TASK-04-03: 중복 공지 제거 (내부 로직, LC-03)

- [ ] 동일/유사 공지 판정 기준: 같은 source + 같은 region + 제목 유사도(단순 문자열 유사도로 시작) → 동일하면 `dedup_group_id`로 묶고 대표 1건만 `published` 처리
- [ ] `/local/collect` 파이프라인 내부에서 처리 (별도 API 없음 — API_DESIGN.md 방침)
- 완료조건(DoD): 동일 공사 공지가 여러 출처에서 중복 수집돼도 사용자 노출 시 1건으로 묶인다

### TASK-04-04: LLM 요약 (내부 로직, LC-04)

- [ ] 원문 → "일시/위치/영향/행동요령" 4항목 구조화 요약 (LLM API 호출, 프롬프트는 이 4항목 고정 스키마로 강제 — JSON mode 사용)
- [ ] LLM 실패/타임아웃 시 원문 그대로 노출 + 요약 상태 플래그로 구분 (전체 요청 실패시키지 않음)
- [ ] `/local/collect` 파이프라인 내부에서 처리, 결과는 `LocalNotice.summary`에 저장되고 `/local/notices` 응답에 포함
- 완료조건(DoD): 샘플 공지 10건 이상에 대해 4항목이 채워진 요약이 생성된다

### TASK-04-05: 내 활동동네 공지 목록 — `GET /api/v1/local/notices` 🔒

- [ ] `User.region_id` 기준으로 `LocalNotice`(status=published) 필터링, 최신순 정렬
- [ ] source(공사/단수/날씨) 쿼리 파라미터로 필터 가능하게
- 완료조건(DoD): 활동동네 미설정 사용자는 400, 설정된 사용자는 해당 지역 공지만 반환

### TASK-04-06: 지도 마커용 공지 목록 — `GET /api/v1/local/notices/map` 🔒

- [ ] `lat`/`lng`가 있는 published 공지만 반환
- [ ] ⚠️ API_DESIGN.md 명시: 크롤링 원본에 좌표가 없는 경우가 확인됨 → **행정동-좌표 매핑 테이블(대표 좌표) 선행 필요**. `Region.lat/lng`(TASK-00-03에서 이미 컬럼 있음)를 fallback으로 사용해 최소한 행정동 대표 좌표로는 지도에 찍히게 처리
- 완료조건(DoD): 공지 원본 좌표가 없어도 `Region` 대표 좌표로 최소 1개 마커는 표시된다 (빈 지도로 남지 않음)
