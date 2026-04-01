from functools import lru_cache

from app.core.config import settings


class ObjectStorageError(RuntimeError):
    pass


def normalize_object_key(value: str) -> str:
    return value.replace('\\', '/').strip('/')


def build_food_relative_dir(food_id: int) -> str:
    return normalize_object_key(f"{settings.food_upload_dir}/{food_id}")


def build_temp_object_key(image_filename: str) -> str:
    return normalize_object_key(f"{settings.storage_root_dir}/{settings.temp_upload_dir}/{image_filename}")


def build_food_object_key(food_relative_dir: str, image_filename: str) -> str:
    return normalize_object_key(f"{settings.storage_root_dir}/{food_relative_dir}/{image_filename}")


def build_public_image_url(food_relative_dir: str | None, image_filename: str | None) -> str | None:
    if not food_relative_dir or not image_filename:
        return None
    object_key = build_food_object_key(food_relative_dir, image_filename)
    domain = settings.cos_public_domain.strip().rstrip('/')
    if not domain:
        return f"/{object_key}"
    if domain.startswith('http://') or domain.startswith('https://'):
        return f"{domain}/{object_key}"
    return f"https://{domain}/{object_key}"


@lru_cache
def get_cos_client():
    try:
        from qcloud_cos import CosConfig, CosS3Client
    except ImportError as exc:
        raise ObjectStorageError(
            'COS SDK is not installed. Please add cos-python-sdk-v5 to requirements.'
        ) from exc

    if not settings.cos_bucket or not settings.cos_region:
        raise ObjectStorageError('COS bucket and region must be configured.')

    secret_id = settings.cos_secret_id.strip()
    secret_key = settings.cos_secret_key.strip()
    if not secret_id or not secret_key:
        raise ObjectStorageError('COS secret id/key must be configured for server-side object moves.')

    config = CosConfig(
        Region=settings.cos_region,
        SecretId=secret_id,
        SecretKey=secret_key,
        Token=settings.cos_session_token.strip() or None,
        Scheme=settings.cos_scheme,
    )
    return CosS3Client(config)


def object_exists(object_key: str) -> bool:
    client = get_cos_client()
    try:
        client.head_object(Bucket=settings.cos_bucket, Key=object_key)
        return True
    except Exception as exc:
        message = str(exc)
        if '404' in message or 'NoSuchResource' in message or 'Not Found' in message:
            return False
        raise ObjectStorageError(f'Failed to inspect object {object_key}: {message}') from exc


def move_object(source_key: str, target_key: str) -> None:
    client = get_cos_client()
    if source_key == target_key:
        return

    copy_source = {
        'Bucket': settings.cos_bucket,
        'Region': settings.cos_region,
        'Key': source_key,
    }
    try:
        client.copy_object(
            Bucket=settings.cos_bucket,
            Key=target_key,
            CopySource=copy_source,
        )
        client.delete_object(Bucket=settings.cos_bucket, Key=source_key)
    except Exception as exc:
        raise ObjectStorageError(
            f'Failed to move object from {source_key} to {target_key}: {exc}'
        ) from exc


def ensure_image_in_food_dir(
    *,
    food_relative_dir: str,
    image_filename: str | None,
    source_food_relative_dir: str | None = None,
) -> None:
    if not image_filename:
        return

    target_key = build_food_object_key(food_relative_dir, image_filename)
    if object_exists(target_key):
        return

    candidate_sources = [build_temp_object_key(image_filename)]
    if source_food_relative_dir and source_food_relative_dir != food_relative_dir:
        candidate_sources.append(build_food_object_key(source_food_relative_dir, image_filename))

    for source_key in candidate_sources:
        if object_exists(source_key):
            move_object(source_key, target_key)
            return

    raise ObjectStorageError(
        f'Image {image_filename} was not found in temp storage or the original food directory.'
    )
