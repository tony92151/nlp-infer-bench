"""Utility helpers for interacting with Amazon S3."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable, Optional

import boto3

LOGGER = logging.getLogger(__name__)


def _client(profile: Optional[str] = None):
    if profile:
        session = boto3.Session(profile_name=profile)
    else:
        session = boto3.Session()
    return session.client("s3")


def upload_directory(
    local_dir: Path | str,
    bucket_uri: str,
    *,
    profile: Optional[str] = None,
) -> str:
    """Upload the contents of ``local_dir`` to ``bucket_uri``.

    Returns the S3 URI of the uploaded directory prefix.
    """

    local_path = Path(local_dir)
    if not local_path.exists():
        raise FileNotFoundError(f"Local directory does not exist: {local_dir}")

    bucket, _, prefix = bucket_uri.partition("/")
    if not bucket:
        raise ValueError(f"Invalid bucket URI: {bucket_uri}")

    client = _client(profile)
    for file_path in local_path.rglob("*"):
        if file_path.is_dir():
            continue
        relative = file_path.relative_to(local_path)
        key = f"{prefix.rstrip('/')}/{relative.as_posix()}" if prefix else relative.as_posix()
        LOGGER.info("Uploading %s to s3://%s/%s", file_path, bucket, key)
        client.upload_file(str(file_path), bucket, key)
    return f"s3://{bucket}/{prefix.rstrip('/') if prefix else ''}".rstrip("/")


def download_prefix(
    bucket_uri: str,
    local_dir: Path | str,
    *,
    profile: Optional[str] = None,
    filters: Optional[Iterable[str]] = None,
) -> Path:
    """Download all objects under ``bucket_uri`` into ``local_dir``."""

    bucket, _, prefix = bucket_uri.partition("/")
    if not bucket:
        raise ValueError(f"Invalid bucket URI: {bucket_uri}")

    local_path = Path(local_dir)
    local_path.mkdir(parents=True, exist_ok=True)

    client = _client(profile)
    paginator = client.get_paginator("list_objects_v2")
    filters_set = set(filters or [])

    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if filters_set and not any(key.endswith(suffix) for suffix in filters_set):
                continue
            relative = key[len(prefix) :].lstrip("/") if prefix else key
            destination = local_path / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            LOGGER.info("Downloading s3://%s/%s to %s", bucket, key, destination)
            client.download_file(bucket, key, str(destination))
    return local_path
