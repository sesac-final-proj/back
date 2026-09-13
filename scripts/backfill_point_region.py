"""꿈방울 region_id 스냅샷 도입 이전에 쌓인 이력 백필.

source="trade"인 PointTransaction은 related_id(WalletTransaction.id)를 따라가면
당시 상품(=거래지역)을 알 수 있다 — 이 값으로 region_id를 채운다.
source="general_payment"는 가맹점(Store)에 위치 정보가 없어 복구 불가, 건드리지 않는다
(admin에 "지역 미확인"으로 계속 남는 게 맞음).

python -m scripts.backfill_point_region 로 실행.
"""
from app.core.db import SessionLocal
from app.models.point import PointTransaction
from app.models.product import Product
from app.models.wallet import WalletTransaction


def main() -> None:
    db = SessionLocal()
    try:
        rows = (
            db.query(PointTransaction)
            .filter(PointTransaction.source == "trade", PointTransaction.region_id.is_(None))
            .all()
        )
        updated = 0
        for row in rows:
            if row.related_id is None:
                continue
            wallet_tx = db.get(WalletTransaction, row.related_id)
            if wallet_tx is None or wallet_tx.product_id is None:
                continue
            product = db.get(Product, wallet_tx.product_id)
            if product is None:
                continue
            row.region_id = product.region_id
            updated += 1
        db.commit()
        print(f"backfilled {updated}/{len(rows)} trade point rows")
    finally:
        db.close()


if __name__ == "__main__":
    main()
