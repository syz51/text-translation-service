"""S3 storage wrapper for audio and SRT files."""

import logging

import aioboto3
import boto3
from botocore.exceptions import ClientError
from fastapi import UploadFile

from app.core.config import settings

logger = logging.getLogger(__name__)


class S3Storage:
    """S3 storage client for managing audio and SRT files."""

    def __init__(self):
        """Initialize S3 storage client."""
        self.session = aioboto3.Session()
        self.sync_session = boto3.Session()
        self.bucket = settings.s3_bucket_name
        self.endpoint_url = settings.s3_endpoint_url
        self.region = settings.s3_region
        self.access_key = settings.s3_access_key_id
        self.secret_key = settings.s3_secret_access_key

    async def init_client(self) -> bool:
        """Initialize and test S3 client connectivity.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            async with self.session.client(
                "s3",
                endpoint_url=self.endpoint_url,
                region_name=self.region,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
            ) as s3:
                # Test connectivity with HEAD bucket
                await s3.head_bucket(Bucket=self.bucket)
            logger.info("S3 client initialized successfully")
            return True
        except ClientError as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error initializing S3 client: {e}")
            return False

    async def upload_audio(self, job_id: str, file: UploadFile) -> str:
        """Upload audio file to S3.

        Args:
            job_id: Job ID for organizing files
            file: Audio file to upload

        Returns:
            S3 key for the uploaded file

        Raises:
            Exception: If upload fails
        """
        s3_key = f"audio/{job_id}/{file.filename}"

        try:
            async with self.session.client(
                "s3",
                endpoint_url=self.endpoint_url,
                region_name=self.region,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
            ) as s3:
                # Stream upload the file
                await s3.upload_fileobj(
                    file.file,
                    self.bucket,
                    s3_key,
                    ExtraArgs={"ContentType": file.content_type or "audio/mpeg"},
                )

            logger.info(f"Uploaded audio file to S3: {s3_key}")
            return s3_key
        except Exception as e:
            logger.error(f"Failed to upload audio file to S3: {e}")
            raise

    async def upload_srt(self, job_id: str, content: str) -> str:
        """Upload SRT file to S3.

        Args:
            job_id: Job ID for organizing files
            content: SRT file content as string

        Returns:
            S3 key for the uploaded file

        Raises:
            Exception: If upload fails
        """
        s3_key = f"srt/{job_id}.srt"

        try:
            async with self.session.client(
                "s3",
                endpoint_url=self.endpoint_url,
                region_name=self.region,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
            ) as s3:
                # Upload SRT content as bytes
                await s3.put_object(
                    Bucket=self.bucket,
                    Key=s3_key,
                    Body=content.encode("utf-8"),
                    ContentType="text/plain; charset=utf-8",
                )

            logger.info(f"Uploaded SRT file to S3: {s3_key}")
            return s3_key
        except Exception as e:
            logger.error(f"Failed to upload SRT file to S3: {e}")
            raise

    async def generate_presigned_url(self, s3_key: str, expiry: int) -> str:
        """Generate presigned URL for S3 object.

        Args:
            s3_key: S3 object key
            expiry: URL expiry time in seconds

        Returns:
            Presigned URL

        Raises:
            Exception: If URL generation fails
        """
        try:
            async with self.session.client(
                "s3",
                endpoint_url=self.endpoint_url,
                region_name=self.region,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
            ) as s3:
                url = await s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.bucket, "Key": s3_key},
                    ExpiresIn=expiry,
                )

            logger.info(f"Generated presigned URL for {s3_key} (expires in {expiry}s)")
            return url
        except Exception as e:
            logger.error(f"Failed to generate presigned URL: {e}")
            raise

    async def test_connectivity(self) -> bool:
        """Test S3 connectivity with HEAD request to bucket.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            async with self.session.client(
                "s3",
                endpoint_url=self.endpoint_url,
                region_name=self.region,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
            ) as s3:
                await s3.head_bucket(Bucket=self.bucket)
            return True
        except Exception as e:
            logger.error(f"S3 connectivity test failed: {e}")
            return False


# Global S3 storage instance
s3_storage = S3Storage()
