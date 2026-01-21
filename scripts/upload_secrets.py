#!/usr/bin/env python3
"""Upload PAM secrets to Azure Key Vault using Azure SDK.

This script reads .env file and uploads secrets to Azure Key Vault.
Uses Azure SDK which works better with corporate proxies than Azure CLI.

Usage:
    python upload_secrets.py kv-npe2-pam-dev-wu2
"""
import os
import sys
from pathlib import Path
from azure.identity import DefaultAzureCredential, InteractiveBrowserCredential
from azure.keyvault.secrets import SecretClient

def load_env_file(env_path):
    """Load .env file and return dict of key-value pairs."""
    env_vars = {}
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            key = key.strip()
            value = value.strip()
            env_vars[key] = value
    return env_vars

def upload_secrets(vault_name, env_vars):
    """Upload secrets to Azure Key Vault."""
    
    vault_url = f"https://{vault_name}.vault.azure.net"
    
    print(f"🔐 Connecting to Key Vault: {vault_url}")
    
    # Try DefaultAzureCredential first (uses existing Azure CLI login if available)
    # If that fails, fall back to interactive browser login
    try:
        credential = DefaultAzureCredential()
        client = SecretClient(vault_url=vault_url, credential=credential)
    except Exception as e:
        print(f"⚠️  DefaultAzureCredential failed, trying interactive login...")
        credential = InteractiveBrowserCredential()
        client = SecretClient(vault_url=vault_url, credential=credential)
    
    # Define secrets to upload (mapping env key -> secret name)
    secrets_to_upload = {
        'PAM_SECRET_KEY': 'PAM-SECRET-KEY',
        'PAM_DB_PASSWORD': 'PAM-DB-PASSWORD',
        'JIRA_API_TOKEN': 'JIRA-API-TOKEN',
        'FABRIC_CLIENT_ID': 'FABRIC-CLIENT-ID',
        'FABRIC_CLIENT_SECRET': 'FABRIC-CLIENT-SECRET',
        'FABRIC_TENANT_ID': 'FABRIC-TENANT-ID',
    }
    
    uploaded = 0
    skipped = 0
    failed = 0
    
    for env_key, secret_name in secrets_to_upload.items():
        value = env_vars.get(env_key, '')
        
        # Skip empty or placeholder values
        if not value or value == 'change_me_dev_only':
            print(f"⚠️  Skipping {secret_name} (empty or placeholder value)")
            skipped += 1
            continue
        
        try:
            print(f"📤 Uploading: {secret_name}")
            client.set_secret(secret_name, value)
            print(f"✅ Successfully uploaded: {secret_name}")
            uploaded += 1
        except Exception as e:
            print(f"❌ Failed to upload {secret_name}: {e}")
            failed += 1
    
    return uploaded, skipped, failed

def main():
    if len(sys.argv) < 2:
        print("Usage: python upload_secrets.py <keyvault-name>")
        print("Example: python upload_secrets.py kv-npe2-pam-dev-wu2")
        sys.exit(1)
    
    vault_name = sys.argv[1]
    
    # Find .env file
    script_dir = Path(__file__).parent
    env_file = script_dir.parent / '.env'
    
    if not env_file.exists():
        print(f"❌ Error: .env file not found at {env_file}")
        sys.exit(1)
    
    print("================================================")
    print("PAM Secrets Upload to Azure Key Vault")
    print("================================================")
    print(f"Vault: {vault_name}")
    print(f"Source: {env_file}")
    print()
    
    # Load environment variables
    env_vars = load_env_file(env_file)
    
    # Upload secrets
    uploaded, skipped, failed = upload_secrets(vault_name, env_vars)
    
    print()
    print("================================================")
    print("📊 Upload Summary")
    print("================================================")
    print(f"✅ Uploaded: {uploaded}")
    print(f"⚠️  Skipped: {skipped}")
    print(f"❌ Failed: {failed}")
    print()
    
    if failed > 0:
        print("⚠️  Some secrets failed to upload. Check permissions.")
        sys.exit(1)
    
    print("✅ Upload Complete!")
    print()
    print("Next Steps:")
    print("1. Configure App Service to reference these secrets:")
    print("   (Azure Portal > App Service > Configuration)")
    print()
    print(f"   PAM_SECRET_KEY = @Microsoft.KeyVault(SecretUri=https://{vault_name}.vault.azure.net/secrets/PAM-SECRET-KEY/)")
    print(f"   PAM_DB_PASSWORD = @Microsoft.KeyVault(SecretUri=https://{vault_name}.vault.azure.net/secrets/PAM-DB-PASSWORD/)")
    print(f"   JIRA_API_TOKEN = @Microsoft.KeyVault(SecretUri=https://{vault_name}.vault.azure.net/secrets/JIRA-API-TOKEN/)")
    print(f"   FABRIC_CLIENT_ID = @Microsoft.KeyVault(SecretUri=https://{vault_name}.vault.azure.net/secrets/FABRIC-CLIENT-ID/)")
    print(f"   FABRIC_CLIENT_SECRET = @Microsoft.KeyVault(SecretUri=https://{vault_name}.vault.azure.net/secrets/FABRIC-CLIENT-SECRET/)")
    print(f"   FABRIC_TENANT_ID = @Microsoft.KeyVault(SecretUri=https://{vault_name}.vault.azure.net/secrets/FABRIC-TENANT-ID/)")
    print()

if __name__ == '__main__':
    main()
