# 서울안전누리 사고·재난 속보 수집기

[서울안전누리](https://safecity.seoul.go.kr/) 화면이 사용하는 사고·재난
속보 JSON 응답을 SQLite에 저장합니다.

## 실행

Python 3.10 이상만 필요하며 외부 패키지는 없습니다.

```powershell
# 10분마다 CSV를 갱신하고 Supabase PostgreSQL에도 자동 업서트 (기본 동작)
python .\safecity_crawler.py

# 한 번만 수집하고 구별 CSV 및 전체 CSV 생성 후 종료
python .\safecity_crawler.py --once

# 특정 구 지정하여 10분마다 수집 (예: 강남구, 서초구, 마포구)
python .\safecity_crawler.py --districts "강남구,서초구,마포구"

# 생성된 전체 CSV를 백엔드 .env의 Supabase PostgreSQL에 업서트
..\.venv\Scripts\python.exe .\upload_to_supabase.py

# DB에 쓰기 전 변환만 검증
..\.venv\Scripts\python.exe .\upload_to_supabase.py --dry-run

# Supabase 업서트 없이 CSV만 갱신
python .\safecity_crawler.py --no-db-sync

# Windows 배치 프로그램으로 10분마다 수집 및 Supabase 업서트
.\run_safecity_batch.bat

# 배치 경로를 한 번만 실행하여 점검
.\run_safecity_batch.bat --once
```

`Ctrl+C`로 안전하게 종료할 수 있습니다.

## 저장 내용

- `safecity_events.csv`: 전체 서울 재난·사고 속보 CSV 파일 (UTF-8-BOM 인코딩)
- `safecity_영등포구.csv`: 영등포구 관련 재난·사고 속보 CSV 파일
- `safecity_송파구.csv`: 송파구 관련 재난·사고 속보 CSV 파일
- `safecity_노원구.csv`: 노원구 관련 재난·사고 속보 CSV 파일
- `fetch_log`: 매 요청의 원본 JSON과 수집 시각. 사이트 응답 구조가 변경될 때
  재처리할 수 있도록 보관합니다.
- `safecity_events.json`: 매 수집 후 현재 사건 전체를 주요 필드와 원본 데이터로
  내보냅니다. 반복 실행 중에는 완성된 새 파일로 한 번에 교체됩니다.
- `upload_to_supabase.py`: 전체 CSV를 `public.nuri_crawled`에
  `source + event_id` 기준으로 업서트합니다. 구별 CSV는 `sigungu` 보강에만
  사용하므로 같은 사건이 중복 저장되지 않습니다.
- 기본 크롤러 실행은 매 수집 직후 위 업로더를 호출합니다. DB 연결이 일시적으로
  실패해도 프로세스는 유지되며 다음 10분 수집 주기에 다시 시도합니다.
- `run_safecity_batch.bat`: 크롤러를 1회 실행한 뒤 600초 대기하는 배치
  프로그램입니다. 실행 로그는 `crawler.batch.log`에 누적됩니다.

## 운영 자동화

운영 환경은 로컬 배치 대신 Supabase Edge Function
`sync-nuri-safecity`를 사용합니다. Supabase Cron 작업
`sync-nuri-safecity-every-10-minutes`가 `*/10 * * * *` 일정으로 함수를
호출하므로 개발 PC가 꺼져 있어도 계속 실행됩니다.

- 함수 소스: `supabase/functions/sync-nuri-safecity/`
- Cron 마이그레이션: `supabase/migrations/20260901022500_schedule_nuri_safecity_sync.sql`
- 롤백 SQL: `supabase/rollback/20260901022500_unschedule_nuri_safecity_sync.sql`

JSON의 최상위 구조는 다음과 같습니다.

```json
{
  "source": "서울안전누리",
  "exported_at": "2026-08-25T16:20:00+09:00",
  "count": 142,
  "events": [
    {
      "event_id": "...",
      "category": "도로돌발",
      "title": "도로돌발-사고",
      "content": "...",
      "occurred_at": "2026-08-25 16:11",
      "coord_x": "205081.366528",
      "coord_y": "439846.166091100000",
      "coord_crs": "EPSG:5186",
      "raw_data": {}
    }
  ]
}
```

사건 유형은 서버가 제공한 유형명을 우선 사용하고, 유형명이 없는 경우 제목과
본문의 키워드로 `단수사고`, `호우`, `화재사고`, `도로돌발`, `기타사고`,
`기타재난` 등을 판정합니다.

## 운영 시 주의

- 사이트 화면과 같은 60초 이상의 호출 간격을 권장합니다.
- 내부 화면용 API이므로 주소나 응답 필드가 변경될 수 있습니다.
- 지도 타일은 복제하지 않습니다. 사건 응답에 좌표가 존재할 때만 좌표 필드에
  저장합니다. `locX`, `locY`로 전달되는 지도 좌표는 `coord_x`, `coord_y`에
  원본 그대로 저장하며 좌표계는 `coord_crs=EPSG:5186`으로 기록합니다.
- 웹 지도에 표시할 때는 `EPSG:5186` 좌표를 `EPSG:4326` 위·경도로 변환하세요.
  안전정보지도의 별도 시설 레이어 수집은 필요한 레이어를 정한 뒤 추가하는
  것이 좋습니다.
