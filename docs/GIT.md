# Git 브랜치 전략

## 브랜치 구조

```
main
└─ release
   └─ staging
      └─ feat/{기능명}
```

- `main`: 건드리지 않는 브랜치. **프로젝트 마지막에 `release`를 병합**할 때만 사용.
- `release`: **배포 기준 브랜치**. `staging`에서 어느 정도 기능이 쌓이고 안정화되면 이 브랜치로 병합해서 배포 가능한 상태를 유지한다.
- `staging`: 개발 통합 브랜치. 모든 `feat/` 브랜치는 여기서 분기하고 여기로 합친다.
- `feat/{기능명}`: 기능 단위 작업 브랜치. `staging`에서 분기.

## 브랜치 네이밍

- 목적에 따라 prefix를 구분한다: `feat/{기능명}`, `fix/{버그명}`, `docs/{문서명}`, `chore/{작업명}`
- 기능명은 영문 kebab-case로 간결하게 작성한다 (예: `feat/trust-contract-crud`)

## 커밋 메시지 컨벤션

- `type: 작업 내용` 형식으로 작성한다.
- type: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`
- 예: `feat: 신탁 계약 조회 API 추가`
- 작업할 때마다 TASK 단위로 commit을 작게 나눠서 쌓는다. 하나의 커밋에 여러 TASK를 몰아넣지 않는다.

## 규칙

1. **main에는 직접 push, PR을 하지 않는다.** main은 프로젝트 마지막에 `release` → `main` 병합 한 번으로만 갱신한다.
2. **release에는 개별 feat 브랜치가 직접 PR을 올리지 않는다.** `staging`이 어느 정도 안정화됐을 때 `staging` → `release`로 병합해 배포 기준을 갱신한다. (병합 시점/주기는 팀 상황에 맞게 정하면 됨 — 예: 스프린트 종료 시, 배포 직전 등)
3. **브랜치는 기능별로 생성**하여 작업한다. 하나의 브랜치에 여러 기능을 섞지 않는다.
4. **PR은 staging으로**, 작업 커밋들을 모아 한 번에 올린다. (`feat/{기능명}` → `staging`)
5. **작업 시작 전 rebase**: `staging`에서 새 브랜치를 파기 전에 반드시 최신 `staging`을 pull 받아 최신 상태로 작업을 시작한다.
   ```bash
   git checkout staging
   git pull origin staging
   git checkout -b feat/{기능명}
   ```
6. **작업 재개 시에도 주기적으로 rebase**: 브랜치를 오래 들고 작업할 경우, 하루 시작할 때/작업을 다시 이어갈 때마다 `staging`을 fetch해서 rebase로 최신 상태를 유지한다. 절차는 아래 "PR 올리기 전 rebase"와 동일.

## PR 전 체크

- 커밋을 기능 단위로 정리했는지 확인
- `staging` 기준 최신화(rebase)했는지 확인
- PR 대상 브랜치가 `staging`인지 확인 (`release`, `main` 아님)

## 작업 중 / PR 올리기 전 rebase (충돌 예방)

작업을 재개할 때, 그리고 PR을 올리기 전에는 그 사이 `staging`에 반영된 다른 사람의 변경사항을 미리 받아 충돌을 로컬에서 먼저 해결한다.

```bash
git fetch origin
git rebase origin/staging
```

- **충돌 없음** → 그대로 `push` 후 PR 진행
- **충돌 있음** → AI 자동 처리로 넘기지 말고 직접 파일을 열어 `staging`의 최신 내용 + 내가 작업한 내용이 함께 동작하도록 수정
  ```bash
  # 충돌난 파일 직접 수정
  git add <파일>
  git rebase --continue
  ```
- rebase는 커밋 히스토리를 다시 쓰므로, 이미 원격에 push했던 브랜치라면 이어서 강제 push가 필요하다.
  ```bash
  git push --force-with-lease
  ```
  (`--force`가 아닌 `--force-with-lease`를 쓴다. 내가 알던 원격 상태 그대로일 때만 덮어써서, 그 사이 다른 사람이 같은 브랜치에 push한 내용을 실수로 날리는 걸 막아준다.)

> 단, 이 절차는 나만 작업하는 개인 feature 브랜치 기준이다. 다른 사람도 pull 받아 같이 쓰는 브랜치에는 force push를 하지 않는다.

## `release` → `staging`으로 반영이 필요할 때

`release`에서 hotfix 등 급한 수정이 발생해 `staging`에 없는 내용이 생겼다면, `staging`에도 반영해서 두 브랜치가 벌어지지 않게 한다.

```bash
git checkout staging
git pull origin staging
git merge release   # 또는 필요 시 특정 커밋만 cherry-pick
git push origin staging
```

---

기존 구조와 달라진 핵심은 **`release`가 `staging`과 `main` 사이의 배포 기준 브랜치로 자리 잡고, `main`은 프로젝트 종료 시점에 `release`를 한 번 병합받는 용도로만 쓰인다**는 점입니다.