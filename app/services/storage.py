import logging
import time
from threading import Lock
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class ObjectStorageError(RuntimeError):
    pass


_cos_auth_cache: dict[str, Any] = {}
_cos_auth_lock = Lock()


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


def _storage_http_client(*, verify: bool = True) -> httpx.Client:
    return httpx.Client(timeout=settings.storage_request_timeout, trust_env=False, verify=verify)


def _request_storage_json(method: str, url: str, *, json_body: dict[str, Any] | None = None, verify: bool = True) -> dict[str, Any]:
    try:
        with _storage_http_client(verify=verify) as client:
            response = client.request(method, url, json=json_body)
            response.raise_for_status()
            return response.json()
    except ValueError as exc:
        raise ObjectStorageError(f'Invalid JSON response from storage helper API: {url}') from exc
    except httpx.HTTPError as exc:
        raise ObjectStorageError(f'Failed to call storage helper API: {url}: {exc}') from exc


def _get_temp_credentials() -> dict[str, Any]:
    now = time.time()
    with _cos_auth_lock:
        expired_time = float(_cos_auth_cache.get('ExpiredTime', 0) or 0)
        if expired_time - now > 60:
            return dict(_cos_auth_cache)

        data = _request_storage_json('GET', settings.wechat_cos_getauth_url, verify=False)
        required_keys = ('TmpSecretId', 'TmpSecretKey', 'Token', 'ExpiredTime')
        if not all(key in data for key in required_keys):
            raise ObjectStorageError('Temporary COS credentials response is incomplete')
        _cos_auth_cache.clear()
        _cos_auth_cache.update(data)
        return dict(_cos_auth_cache)


def _build_cos_client():
    try:
        from qcloud_cos import CosConfig, CosS3Client
    except ImportError as exc:
        raise ObjectStorageError('COS SDK is not installed. Please add cos-python-sdk-v5 to requirements.') from exc

    if not settings.cos_bucket or not settings.cos_region:
        raise ObjectStorageError('COS bucket and region must be configured.')

    if settings.cos_secret_id.strip() and settings.cos_secret_key.strip():
        config = CosConfig(
            Region=settings.cos_region,
            SecretId=settings.cos_secret_id.strip(),
            SecretKey=settings.cos_secret_key.strip(),
            Token=settings.cos_session_token.strip() or None,
            Scheme=settings.cos_scheme,
        )
        return CosS3Client(config)

    auth = _get_temp_credentials()
    config = CosConfig(
        Region=settings.cos_region,
        SecretId=auth['TmpSecretId'],
        SecretKey=auth['TmpSecretKey'],
        Token=auth['Token'],
        Scheme=settings.cos_scheme,
    )
    return CosS3Client(config)


def _get_meta_fileid(*, openid: str, object_key: str) -> str:
    payload = {
        'openid': openid,
        'bucket': settings.cos_bucket,
        'paths': [f'/{normalize_object_key(object_key)}'],
    }
    data = _request_storage_json('POST', settings.wechat_cos_meta_encode_url, json_body=payload, verify=False)
    if data.get('errcode') not in (None, 0):
        raise ObjectStorageError(f"Failed to encode COS metadata: {data.get('errmsg', 'unknown error')}")
    respdata = data.get('respdata') or {}
    fields = respdata.get('x_cos_meta_field_strs') or []
    if not fields:
        raise ObjectStorageError('COS metadata encode returned no x-cos-meta-fileid value')
    return fields[0]


def _head_object(object_key: str) -> dict[str, Any] | None:
    client = _build_cos_client()
    try:
        return client.head_object(Bucket=settings.cos_bucket, Key=object_key)
    except Exception as exc:
        message = str(exc)
        if '404' in message or 'NoSuchResource' in message or 'Not Found' in message:
            return None
        raise ObjectStorageError(f'Failed to inspect object {object_key}: {message}') from exc


def object_exists(object_key: str) -> bool:
    return _head_object(object_key) is not None


def move_object(*, source_key: str, target_key: str, openid: str = '') -> None:
    client = _build_cos_client()
    if source_key == target_key:
        return

    source_head = _head_object(source_key)
    if source_head is None:
        raise ObjectStorageError(f'Source object does not exist: {source_key}')

    try:
        meta_fileid = _get_meta_fileid(openid=openid, object_key=target_key)
    except Exception as exc:
        logger.exception('Failed to prepare COS metadata for target object: %s', target_key)
        raise ObjectStorageError(f'Failed to prepare metadata for {target_key}: {exc}') from exc

    copy_source = {
        'Bucket': settings.cos_bucket,
        'Region': settings.cos_region,
        'Key': source_key,
    }

    copy_kwargs: dict[str, Any] = {
        'Bucket': settings.cos_bucket,
        'Key': target_key,
        'CopySource': copy_source,
        'CopyStatus': 'Replaced',
        'Metadata': {'x-cos-meta-fileid': meta_fileid},
    }

    content_type = source_head.get('ContentType')
    if content_type:
        copy_kwargs['ContentType'] = content_type
    cache_control = source_head.get('CacheControl')
    if cache_control:
        copy_kwargs['CacheControl'] = cache_control
    content_disposition = source_head.get('ContentDisposition')
    if content_disposition:
        copy_kwargs['ContentDisposition'] = content_disposition
    content_encoding = source_head.get('ContentEncoding')
    if content_encoding:
        copy_kwargs['ContentEncoding'] = content_encoding
    content_language = source_head.get('ContentLanguage')
    if content_language:
        copy_kwargs['ContentLanguage'] = content_language

    try:
        client.copy_object(**copy_kwargs)
        logger.info('Copied object from %s to %s', source_key, target_key)
    except Exception as exc:
        logger.exception('COS copy_object failed. source=%s target=%s copy_source=%s', source_key, target_key, copy_source)
        raise ObjectStorageError(f'Failed to copy object from {source_key} to {target_key}: {exc}') from exc

    try:
        client.delete_object(Bucket=settings.cos_bucket, Key=source_key)
        logger.info('Deleted source object after copy: %s', source_key)
    except Exception as exc:
        logger.exception('COS delete_object failed after successful copy. source=%s target=%s', source_key, target_key)
        raise ObjectStorageError(f'Copied to {target_key} but failed to delete source {source_key}: {exc}') from exc


def ensure_image_in_food_dir(
    *,
    food_relative_dir: str,
    image_filename: str | None,
    openid: str = '',
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
            move_object(source_key=source_key, target_key=target_key, openid=openid)
            logger.info('Moved object from %s to %s', source_key, target_key)
            return

    raise ObjectStorageError(f'Image {image_filename} was not found in temp storage or the original food directory.')
