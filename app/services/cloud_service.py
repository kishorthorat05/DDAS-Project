"""
Cloud storage integration: AWS S3, Google Cloud Storage, Azure Blob, etc.
Handles multi-cloud uploads, syncing, and multi-source data integration.
"""
import json
from typing import Dict, List, Optional
from cryptography.fernet import Fernet
import os

from app.models.database import get_db, row_to_dict, rows_to_list
from config.settings import get_config

Config = get_config()

# Supported cloud providers
CLOUD_PROVIDERS = {
    "aws_s3": {"name": "Amazon S3", "required_fields": ["bucket_name", "region", "access_key", "secret_key"]},
    "gcs": {"name": "Google Cloud Storage", "required_fields": ["bucket_name", "access_key"]},
    "azure_blob": {"name": "Azure Blob Storage", "required_fields": ["bucket_name", "access_key"]},
    "sftp": {"name": "SFTP Server", "required_fields": ["endpoint", "access_key"]},
    "ftp": {"name": "FTP Server", "required_fields": ["endpoint", "access_key", "secret_key"]},
}


def get_cipher():
    """Get encryption cipher for secrets."""
    # In production, use AWS Secrets Manager, HashiCorp Vault, etc.
    key = os.getenv("ENCRYPTION_KEY", "default-insecure-key-change-in-production")
    return Fernet(Fernet.generate_key() if len(key) < 32 else key.ljust(44, '=').encode())


def encrypt_secret(secret: str) -> str:
    """Encrypt sensitive data."""
    try:
        cipher = get_cipher()
        encrypted = cipher.encrypt(secret.encode())
        return encrypted.decode()
    except Exception:
        return secret  # Fallback


def decrypt_secret(encrypted: str) -> str:
    """Decrypt sensitive data."""
    try:
        cipher = get_cipher()
        decrypted = cipher.decrypt(encrypted.encode())
        return decrypted.decode()
    except Exception:
        return encrypted  # Fallback


def create_cloud_integration(org_id: str, provider: str, name: str,
                             config: Dict) -> Optional[dict]:
    """Create a new cloud integration."""
    if provider not in CLOUD_PROVIDERS:
        return None
    
    # Validate required fields
    required = CLOUD_PROVIDERS[provider]["required_fields"]
    if not all(config.get(field) for field in required):
        return None
    
    with get_db() as conn:
        integration_id = f"cloud_{provider}_{org_id}"[:40]
        
        try:
            conn.execute(
                """INSERT INTO cloud_integrations 
                   (id, organization_id, provider, name, bucket_name, endpoint, 
                    access_key, secret_key, region, is_active)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (integration_id, org_id, provider, name,
                 config.get("bucket_name"), config.get("endpoint"),
                 encrypt_secret(config.get("access_key", "")),
                 encrypt_secret(config.get("secret_key", "")),
                 config.get("region"), 1)
            )
            return {
                "id": integration_id,
                "provider": provider,
                "name": name,
                "is_active": True
            }
        except Exception as e:
            return None


def get_cloud_integration(org_id: str, provider: str = None) -> List[dict]:
    """Get cloud integrations for organization."""
    with get_db() as conn:
        if provider:
            integrations = rows_to_list(conn.execute(
                """SELECT id, organization_id, provider, name, endpoint, bucket_name, 
                          region, is_active, sync_enabled, last_sync
                   FROM cloud_integrations
                   WHERE organization_id = ? AND provider = ? AND is_active = 1""",
                (org_id, provider)
            ).fetchall())
        else:
            integrations = rows_to_list(conn.execute(
                """SELECT id, organization_id, provider, name, endpoint, bucket_name,
                          region, is_active, sync_enabled, last_sync
                   FROM cloud_integrations
                   WHERE organization_id = ? AND is_active = 1""",
                (org_id,)
            ).fetchall())
    
    return integrations


def upload_to_cloud(integration_id: str, file_path: str, cloud_path: str) -> bool:
    """Upload file to cloud storage."""
    with get_db() as conn:
        integration = row_to_dict(conn.execute(
            "SELECT provider, bucket_name, endpoint, access_key, secret_key FROM cloud_integrations WHERE id = ?",
            (integration_id,)
        ).fetchone())
    
    if not integration:
        return False
    
    try:
        provider = integration["provider"]
        
        if provider == "aws_s3":
            return _upload_s3(
                bucket=integration["bucket_name"],
                access_key=decrypt_secret(integration["access_key"]),
                secret_key=decrypt_secret(integration["secret_key"]),
                file_path=file_path,
                object_key=cloud_path
            )
        
        elif provider == "gcs":
            return _upload_gcs(
                bucket=integration["bucket_name"],
                credentials=decrypt_secret(integration["access_key"]),
                file_path=file_path,
                object_name=cloud_path
            )
        
        elif provider == "azure_blob":
            return _upload_azure(
                container=integration["bucket_name"],
                connection_string=decrypt_secret(integration["secret_key"]),
                file_path=file_path,
                blob_name=cloud_path
            )
        
        elif provider == "sftp":
            return _upload_sftp(
                host=integration["endpoint"],
                username=decrypt_secret(integration["access_key"]),
                password=decrypt_secret(integration["secret_key"]),
                local_path=file_path,
                remote_path=cloud_path
            )
        
    except Exception as e:
        print(f"[Cloud Upload Error] {e}")
        return False
    
    return False


def _upload_s3(bucket: str, access_key: str, secret_key: str, 
               file_path: str, object_key: str) -> bool:
    """Upload to AWS S3."""
    try:
        import boto3
        s3 = boto3.client(
            's3',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key
        )
        s3.upload_file(file_path, bucket, object_key)
        return True
    except Exception:
        return False


def _upload_gcs(bucket: str, credentials: str, file_path: str, object_name: str) -> bool:
    """Upload to Google Cloud Storage."""
    try:
        from google.cloud import storage
        from io import BytesIO
        import json as json_lib
        
        creds = json_lib.loads(credentials)
        client = storage.Client.from_service_account_info(creds)
        bucket_obj = client.bucket(bucket)
        blob = bucket_obj.blob(object_name)
        blob.upload_from_filename(file_path)
        return True
    except Exception:
        return False


def _upload_azure(container: str, connection_string: str, 
                  file_path: str, blob_name: str) -> bool:
    """Upload to Azure Blob Storage."""
    try:
        from azure.storage.blob import BlobServiceClient
        client = BlobServiceClient.from_connection_string(connection_string)
        blob_client = client.get_blob_client(container=container, blob=blob_name)
        with open(file_path, "rb") as f:
            blob_client.upload_blob(f)
        return True
    except Exception:
        return False


def _upload_sftp(host: str, username: str, password: str,
                 local_path: str, remote_path: str) -> bool:
    """Upload via SFTP."""
    try:
        import paramiko
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(host, username=username, password=password)
        sftp = ssh.open_sftp()
        sftp.put(local_path, remote_path)
        sftp.close()
        ssh.close()
        return True
    except Exception:
        return False


def sync_cloud_storage(org_id: str, provider: str = None) -> Dict:
    """Sync files with cloud storage."""
    result = {
        "synced": 0,
        "failed": 0,
        "skipped": 0,
        "errors": []
    }
    
    integrations = get_cloud_integration(org_id, provider)
    
    for integration in integrations:
        if not integration.get("sync_enabled"):
            continue
        
        with get_db() as conn:
            # Get datasets to sync
            datasets = rows_to_list(conn.execute(
                """SELECT id, file_path, file_name FROM datasets
                   WHERE organization_id = ? AND source_location = 'Local'
                   LIMIT 100""",
                (org_id,)
            ).fetchall())
        
        for ds in datasets:
            try:
                cloud_path = f"{org_id}/{ds['id']}/{ds['file_name']}"
                if upload_to_cloud(integration["id"], ds["file_path"], cloud_path):
                    result["synced"] += 1
                else:
                    result["failed"] += 1
            except Exception as e:
                result["failed"] += 1
                result["errors"].append(str(e))
    
    return result


def list_cloud_files(org_id: str, provider: str, prefix: str = "") -> List[Dict]:
    """List files in cloud storage."""
    integrations = get_cloud_integration(org_id, provider)
    
    if not integrations:
        return []
    
    files = []
    for integration in integrations:
        try:
            # Implementation depends on provider
            # This is a placeholder
            pass
        except Exception:
            pass
    
    return files
