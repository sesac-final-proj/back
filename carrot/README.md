# 가지마켓 백엔드 격리 영역

현재 프론트 구현은 Next 앱 내부 목업 상태로 동작합니다.

`back/carrot`는 기존 FastAPI 파일과 충돌하지 않도록 만든 임시 계약 영역입니다. 실제 API 연결 시 이 데이터 모양을 기준으로 `products`, `community_posts`, `chat_rooms`, `local_businesses` 엔드포인트를 붙이면 됩니다.
