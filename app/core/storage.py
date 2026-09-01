"""NCP Object Storage (S3 호환) 클라이언트.

업로드는 프록시하지 않는다 — 서버가 발급한 presigned URL로 클라이언트가
NCP에 직접 PUT하고, 서버는 완료된 object_key만 등록받는다. 이미지 바이트가
FastAPI를 거치지 않아 서버 부하/타임아웃 걱정이 없다.
"""
import uuid
from functools import lru_cache

import boto3
from botocore.config import Config

from app.core.config import settings

ALLOWED_CONTENT_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
PRESIGN_EXPIRE_SECONDS = 300


@lru_cache
def _client():
    return boto3.client(
        "s3",
        endpoint_url=settings.NCP_ENDPOINT,
        aws_access_key_id=settings.NCP_ACCESS_KEY,
        aws_secret_access_key=settings.NCP_SECRET_KEY,
        region_name=settings.NCP_REGION,
        config=Config(s3={"addressing_style": "path"}),
    )


def build_object_key(product_id: int, content_type: str) -> str:
    ext = ALLOWED_CONTENT_TYPES.get(content_type)
    if ext is None:
        raise ValueError(f"지원하지 않는 이미지 형식입니다: {content_type}")
    return f"products/{product_id}/{uuid.uuid4().hex}.{ext}"


def public_url(object_key: str) -> str:
    return f"{settings.NCP_ENDPOINT}/{settings.NCP_BUCKET}/{object_key}"


def presigned_put_url(object_key: str, content_type: str) -> str:
    return _client().generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.NCP_BUCKET,
            "Key": object_key,
            "ContentType": content_type,
            "ACL": "public-read",
        },
        ExpiresIn=PRESIGN_EXPIRE_SECONDS,
    )


def delete_object(object_key: str) -> None:
    _client().delete_object(Bucket=settings.NCP_BUCKET, Key=object_key)
