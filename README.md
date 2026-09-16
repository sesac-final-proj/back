# back
# to the

## 로컬 실행

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 값 채우기 (DB_*, JWT_SECRET 등)

alembic upgrade head        # DB 마이그레이션 적용
uvicorn app.main:app --reload
```

- API 문서: http://127.0.0.1:8000/docs
- 브랜치 전략: [docs/GIT.md](docs/GIT.md)
- API 설계 및 이슈 목록: [docs/API_DESIGN.md](docs/API_DESIGN.md), [docs/issue/](docs/issue/)

## 마이그레이션

모델을 바꾼 뒤에는 새 리비전을 만들고 적용한다.

```bash
alembic revision --autogenerate -m "설명"
alembic upgrade head
```
