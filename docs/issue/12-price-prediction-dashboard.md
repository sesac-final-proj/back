# 가격예측 모델 대시보드 (price-prediction-dashboard)

> 브랜치: `feat/price-prediction-dashboard`
> 우선순위: 2순위 (어드민 부가 기능 — [04-admin.md](04-admin.md) AD-01/02 이후)
> API prefix: `/api/v1/admin` (기존 어드민 라우터에 엔드포인트만 추가, 태그: `어드민`)
> 관련 문서: [API_DESIGN.md](../API_DESIGN.md), `analyzer/` 프로젝트의 `docs/모델_결과_요약.md`, `docs/플랫폼_비교_분석_방법론.md`

## 개요

`analyzer/` 프로젝트(별도 리포지토리 성격의 데이터분석 파이프라인)에서 만든 당근마켓 중고거래 가격예측(LightGBM) 결과를 어드민 대시보드의 "가격 모델" 섹션에서 보여준다. 현재 프론트(`front/src/components/admin/sections/PriceModelSection.tsx`)는 `public/model-validation.json` 정적 파일을 그대로 fetch하는 임시 상태이고, 그 데이터도 이번 분석과는 다른 모델(RandomForest/LightGBM, 등록가 기준)이다. 이 이슈는:

1. `analyzer/outputs/`의 산출물(`metrics.json`, `viz_전처리완료.csv`)을 실제 API 응답으로 대체
2. 세부유형별 가격분포(스웜 플롯용 원천 데이터) 조회 엔드포인트 신설

두 가지를 다룬다. 프론트 구현 계획은 [front/docs/PRICE_PREDICTION_DASHBOARD.md](../../../front/docs/PRICE_PREDICTION_DASHBOARD.md) 참고.

## 선행 조건

- [04-admin.md](04-admin.md)의 `require_admin` Dependency 및 어드민 라우터 skeleton
- `analyzer/outputs/metrics.json`, `analyzer/outputs/viz_전처리완료.csv` 존재 (analyzer 파이프라인 실행 완료 산출물)

## 데이터 원천

새 DB 테이블 없이 **파일 기반**으로 시작한다 — 모델을 재학습할 때마다 `analyzer/` 쪽에서 파일을 새로 생성하고, 백엔드는 그 파일을 읽어서 응답만 변환한다. 재학습 빈도가 낮고(수동 실행) 실시간성이 필요 없는 배치성 산출물이라 DB 적재는 과설계 — 필요해지면 그때 테이블화한다.

- `analyzer/outputs/metrics.json` — 피처셋(`full`/`no_leak_prone`)별 R²/RMSE/MAE/MAPE/Hit@10/Hit@20, 최종 결과 요약에 그대로 대응
- `analyzer/outputs/viz_전처리완료.csv` — `카테고리`, `세부유형`, `가격원` 등 15열, 프론트 스웜 플롯의 원천 데이터
- 배포 시 이 두 파일을 백엔드가 읽을 수 있는 고정 경로에 복사해두거나(`back/app/data/price_model/`), 두 리포지토리가 분리돼 있으면 CI에서 파일을 복사하는 단계 추가 — 경로는 `settings.PRICE_MODEL_DATA_DIR` 환경변수로 뺀다(하드코딩 금지)

## Task 목록

### TASK-12-01: 모델 지표 조회 — `GET /api/v1/admin/price-model/metrics` 🔒(admin)

- [ ] `metrics.json`을 읽어 그대로/가공 없이 반환 (필드명 변환이 필요하면 최소한으로)
- [ ] 응답 예시:
  ```json
  {
    "final": {
      "model": "LightGBM",
      "featureSet": "no_leak_prone",
      "r2": 0.752,
      "rmse": 47445,
      "mae": 30520,
      "mape": 0.45,
      "hitAt10": 0.25,
      "hitAt20": 0.80,
      "rangeCoverage2575": 0.521,
      "rangeCoverage1090": 0.822,
      "trainRows": 11723
    },
    "baseline": { "model": "RandomForest", "r2": 0.737, "rmse": 48931, "hitAt20": 0.432 }
  }
  ```
- [ ] `metrics.json`이 없거나 파싱 실패 시 500이 아니라 `503` + 명확한 에러 메시지("모델 산출물이 아직 없습니다") — 배치 산출물 부재는 서버 장애가 아니라 데이터 부재이므로 구분
- 완료조건(DoD): admin 토큰으로 최종/베이스라인 지표 반환, 파일 없을 때 503, 일반 user 토큰 403

### TASK-12-02: 세부유형별 가격분포 조회 — `GET /api/v1/admin/price-model/price-distribution` 🔒(admin)

- [ ] 쿼리 파라미터: `category`(선택, 미지정 시 전체 카테고리 각각의 상위 5개 세부유형 + "기타" 묶음)
- [ ] `viz_전처리완료.csv`를 읽어 카테고리별로 그룹화, 세부유형은 건수 기준 상위 5개만 이름 유지하고 나머지는 `"기타"`로 합쳐서 반환 (프론트에서 매번 계산하지 않도록 서버가 미리 묶음)
- [ ] 응답 예시:
  ```json
  {
    "categories": [
      {
        "category": "마미케어",
        "sampleCount": 3861,
        "types": [
          { "type": "일반", "count": 2737, "medianPrice": 162000 },
          { "type": "미니", "count": 626, "medianPrice": 60000 }
        ],
        "points": [{ "type": "일반", "price": 190000 }, ...]
      }
    ]
  }
  ```
- [ ] `points` 배열이 카테고리당 최대 ~3,800건까지 나갈 수 있음 — 응답 크기가 부담되면 `sample`(선택, 기본 2000) 파라미터로 랜덤 다운샘플링 지원 (좌표 흩뿌림 시각화라 전수가 필수는 아님)
- 완료조건(DoD): 존재하지 않는 `category` 값 → 빈 `categories` 배열(404 아님, 필터 결과 없음과 동일 취급), 정상 요청 시 위 스키마로 반환

## 비고

- 이 두 엔드포인트는 회귀 모델 하나의 스냅샷을 보여주는 용도라 페이지네이션 불필요 (`app.core.pagination.Page[T]` 미적용).
- `analyzer/`가 별도 리포지토리로 완전히 분리되면(현재는 같은 프로젝트 폴더 하위) 파일 복사 대신 S3/오브젝트 스토리지 경유로 바꾸는 걸 고려 — 지금은 로컬 파일 읽기로 충분.
