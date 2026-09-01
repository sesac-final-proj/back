from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1.local import schema


def _compact(value: object, limit: int = 82) -> str:
    content = str(value or "").strip()
    if len(content) <= limit:
        return content
    return f"{content[: limit - 1]}..."


def _format_summary(risk_type: str | None, address: str | None, description: str | None) -> str:
    pieces = [_compact(risk_type, 32), _compact(address, 58), _compact(description, 82)]
    summary = " · ".join(piece for piece in pieces if piece)
    return summary or "서울안전누리 위험신호"


def list_danger_signals(
    db: Session,
    sigungu: str | None,
    q: str | None,
    limit: int,
) -> schema.DangerSignalListResponse:
    filters = [
        "source = 'seoul_safecity'",
        "latitude is not null",
        "longitude is not null",
    ]
    params: dict[str, object] = {"limit": limit}

    if sigungu:
        filters.append(
            """
            (
              sigungu = :sigungu
              or raw_data->'matched_districts' ? :sigungu
              or address ilike :sigungu_like
              or risk_name ilike :sigungu_like
              or description ilike :sigungu_like
            )
            """
        )
        params["sigungu"] = sigungu
        params["sigungu_like"] = f"%{sigungu}%"

    if q:
        filters.append(
            """
            (
              risk_name ilike :q
              or risk_type ilike :q
              or address ilike :q
              or description ilike :q
            )
            """
        )
        params["q"] = f"%{q}%"

    where_clause = " and ".join(f"({part})" for part in filters)
    rows = db.execute(
        text(
            f"""
            select
              coalesce(external_id, id::text) as id,
              risk_type,
              risk_name,
              address,
              coalesce(sigungu, raw_data->'matched_districts'->>0) as sigungu,
              latitude,
              longitude,
              description,
              observed_at,
              source_url
            from public.nuri_crawled
            where {where_clause}
            order by coalesce(observed_at, crawled_at) desc nulls last, id desc
            limit :limit
            """
        ),
        params,
    ).mappings().all()

    items = [
        schema.DangerSignalItem(
            id=str(row["id"]),
            name=_compact(row["risk_name"] or row["address"] or row["risk_type"] or "서울안전누리 위험신호", 80),
            neighborhood_name=row["sigungu"],
            sigungu=row["sigungu"],
            distance="실시간",
            summary=_format_summary(row["risk_type"], row["address"], row["description"]),
            lat=float(row["latitude"]),
            lng=float(row["longitude"]),
            risk_type=row["risk_type"],
            observed_at=row["observed_at"],
            source_url=row["source_url"],
        )
        for row in rows
    ]

    return schema.DangerSignalListResponse(items=items, total=len(items))
