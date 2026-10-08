"""C11 thin S3-compatible Artifact Payload provider.

All bytes stay within Data Plane and object storage, not Native History/PG.
Endpoint credentials are process-local; only opaque storage refs are persisted.
"""
from __future__ import annotations

import hashlib
import os
from urllib.parse import urlparse
import boto3
from botocore.config import Config


class S3PayloadStore:
    def __init__(self):
        endpoint=os.environ["POC_C11_S3_ENDPOINT"]
        if urlparse(endpoint).hostname not in ("127.0.0.1","localhost"):
            # C11 sandbox demo has no IAM/Secret Manager; never expose it on
            # arbitrary endpoints using weak POC-only credentials.
            raise ValueError("C11 POC S3 endpoint must be loopback only")
        self.bucket=os.environ.get("POC_C11_S3_BUCKET","poc-c11-artifacts")
        self.s3=boto3.client(
            "s3",endpoint_url=endpoint,
            aws_access_key_id=os.environ.get("POC_C11_S3_ACCESS_KEY","poc"),
            aws_secret_access_key=os.environ.get("POC_C11_S3_SECRET_KEY","poc"),
            region_name="us-east-1",
            config=Config(s3={"addressing_style":"path"},
                          retries={"max_attempts":2}))
        # POC-only bucket lifecycle. Not a retention service.
        if self.bucket not in [b["Name"] for b in self.s3.list_buckets()["Buckets"]]:
            self.s3.create_bucket(Bucket=self.bucket)

    def put(self, key: str, data: bytes) -> str:
        self.s3.put_object(Bucket=self.bucket,Key=key,Body=data,
                           ContentType="application/octet-stream",
                           Metadata={"sha256":hashlib.sha256(data).hexdigest()})
        return "s3://"+self.bucket+"/"+key

    def read(self, ref: str) -> bytes:
        if not ref.startswith("s3://"+self.bucket+"/"):
            raise ValueError("S3 ref outside expected bucket")
        key=ref[len("s3://"+self.bucket+"/"):]
        result=self.s3.get_object(Bucket=self.bucket,Key=key)
        return result["Body"].read()

    def delete(self, ref: str):
        if not ref.startswith("s3://"+self.bucket+"/"):
            raise ValueError("Invalid ref")
        self.s3.delete_object(Bucket=self.bucket,
                              Key=ref[len("s3://"+self.bucket+"/"):])
