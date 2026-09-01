# Issue 목록 (당근 지역생활 고도화 프로젝트)

> 근거: [PRD](../API_DESIGN.md 상단 참고) / [API_DESIGN.md](../API_DESIGN.md)
>
> `app/` 코드가 아직 없는 초기 단계라, EPIC(API_DESIGN.md의 라우터 단위) + 공통 인프라를 기준으로 이슈를 나눴다. 각 파일은 하나의 `feat/{기능명}` 브랜치 단위로 작업하기 좋은 크기로 쪼갰다 (`docs/GIT.md` 브랜치 전략 참고).

## 작업 순서 (우선순위 기준)

| 순서 | 파일 | EPIC | 우선순위 | 비고 |
| --- | --- | --- | --- | --- |
| 0 | [01-common-infra.md](01-common-infra.md) | 공통 인프라 | 선행 | 모든 EPIC의 전제조건 |
| 1 | [02-auth.md](02-auth.md) | 회원관리 | 1순위 | 인증 없이는 다른 EPIC 진행 불가 |
| 1.5 | [10-marketplace-core.md](10-marketplace-core.md) | 중고거래(기본 마켓) | 실질적 선행 | 상품 등록/조회/채팅 — 기존 이슈 문서엔 없던 PRD TR-00 부분, `carrot/mock_contract.py` mock을 실제 API로 대체 |
| 2 | [03-trades.md](03-trades.md) | 중고거래(가격분석) | 1순위 | 적정가격·거래빈도 분석. 10-marketplace-core와 별도 브랜치 |
| 3 | [04-admin.md](04-admin.md) | 어드민 (데이터 현황) | 1순위 | AD-01, AD-02만 1순위 |
| 4 | [05-local.md](05-local.md) | 갖가지 | 1순위 | |
| 5 | [06-dream.md](06-dream.md) | 꿈가지 | 1순위 | |
| 6 | [07-local-share.md](07-local-share.md) | 지역상생 | 1순위 | |
| 7 | [08-buyer-ai.md](08-buyer-ai.md) | 구매자AI | BA-01 1순위 / BA-02 2순위 | |
| 8 | [09-backlog-2nd-3rd.md](09-backlog-2nd-3rd.md) | 전 EPIC 2·3순위 | 2/3순위 | 플랫폼 비교, 재판매가, 기부 관리 등 |

## 사용 방법

1. 이슈 파일 하나 = 브랜치 하나. 파일명 기준으로 `feat/{기능명}` 브랜치를 판다.
   ```bash
   git checkout staging
   git pull origin staging
   git checkout -b feat/auth
   ```
2. 각 파일 안의 `TASK-xx-N` 단위로 커밋을 쪼갠다 (`docs/GIT.md`: "TASK 단위로 commit을 작게 나눠서 쌓는다").
3. 완료조건(DoD)을 모두 만족하면 해당 TASK 체크박스를 체크하고 PR은 `staging`으로 올린다.

## 공통 규칙 (모든 이슈 공통)

- 라우터 구조는 `router.py` / `service.py` / `schema.py` 3분리 (API_DESIGN.md 컨벤션)
- 인증 필요 API는 `Depends(get_current_user)`, 관리자 전용은 `Depends(require_admin)` 사용
- prefix는 `/api/v1/{epic}` 고정, 태그는 한글 EPIC명
- 각 TASK는 실패 케이스(422/401/403/404)까지 완료조건에 포함한다 — 성공 케이스만 만들고 끝내지 않는다
