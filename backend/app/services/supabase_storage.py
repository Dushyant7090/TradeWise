"""
Supabase Storage service for file uploads
"""
import logging
import os
from flask import current_app

logger = logging.getLogger(__name__)


class SupabaseStorageService:
    """Upload/delete files in Supabase Storage."""

    def _get_client(self):
        from supabase import create_client
        url = current_app.config.get("SUPABASE_URL", "")
        key = current_app.config.get("SUPABASE_SERVICE_ROLE_KEY", "")
        if not url or not key:
            raise ValueError("Supabase URL and service role key are required")
        return create_client(url, key)

    def upload_file(self, bucket: str, path: str, file_data: bytes, content_type: str = "application/octet-stream") -> str:
        """
        Upload a file to Supabase Storage.
        Returns the public URL of the uploaded file.
        """
        client = self._get_client()
        try:
            result = client.storage.from_(bucket).upload(
                path=path,
                file=file_data,
                file_options={"content-type": content_type, "upsert": "true"},
            )
            # Get public URL
            public_url = client.storage.from_(bucket).get_public_url(path)
            return public_url
        except Exception as e:
            logger.error(f"Supabase storage upload error: {e}")
            raise

    def delete_file(self, bucket: str, path: str) -> bool:
        """Delete a file from Supabase Storage."""
        client = self._get_client()
        try:
            client.storage.from_(bucket).remove([path])
            return True
        except Exception as e:
            logger.error(f"Supabase storage delete error: {e}")
            return False

    def get_signed_url(self, bucket: str, path: str, expires_in: int = 3600) -> str:
        """Get a signed (temporary) URL for a private file."""
        client = self._get_client()
        try:
            result = client.storage.from_(bucket).create_signed_url(path, expires_in)
            return result.get("signedURL", "")
        except Exception as e:
            logger.error(f"Supabase storage signed URL error: {e}")
            raise


supabase_storage = SupabaseStorageService()
