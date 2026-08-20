"""Unit tests for the Database Backup and Verification system."""


from scripts.backup_db import (
    get_db_engine_type,
    execute_backup,
    verify_backup,
    manage_retention,
    BACKUP_DIR,
)
from backend.app.services.storage_service import get_storage_provider


def test_get_db_engine_type():
    engine_type = get_db_engine_type()
    assert engine_type in ("sqlite", "postgres")


def test_execute_and_verify_backup():
    # Run backup snapshot
    dest_path, slug = execute_backup()
    assert dest_path.exists()
    assert slug.startswith("backups/db_backup_")

    # Verify upload & restore viability
    provider = get_storage_provider()
    # Ensure file is registered with provider locally
    provider.upload_file(dest_path, slug)

    verified = verify_backup(slug)
    assert verified is True

    # Cleanup local files
    if dest_path.exists():
        dest_path.unlink()
    provider.delete_file(slug)


def test_retention_pruning():
    provider = get_storage_provider()

    # Define test dummy files
    slug_old = "backups/db_backup_old.sql.gz"
    slug_new = "backups/db_backup_new.sql.gz"

    file_old = BACKUP_DIR / "db_backup_old.sql.gz"
    file_new = BACKUP_DIR / "db_backup_new.sql.gz"

    with open(file_old, "w") as f:
        f.write("mock old")
    with open(file_new, "w") as f:
        f.write("mock new")

    provider.upload_file(file_old, slug_old)
    provider.upload_file(file_new, slug_new)

    # Mock manifest with an old date and a new date
    manifest_slug = "backups/manifest.json"
    manifest_local_path = BACKUP_DIR / "manifest.json"

    from datetime import datetime, timezone
    import json
    now_iso = datetime.now(timezone.utc).isoformat()
    mock_manifest = [
        {"slug": slug_old, "created_at": "2020-01-01T00:00:00+00:00"},
        {"slug": slug_new, "created_at": now_iso},
    ]

    with open(manifest_local_path, "w") as f:
        json.dump(mock_manifest, f, indent=2)
    provider.upload_file(manifest_local_path, manifest_slug)

    # Run retention (retention limit is 7 days, so 2020 backup should be deleted)
    manage_retention(slug_new)

    # Check manifest updated
    manifest_verified = provider.get_file(manifest_slug)
    with open(manifest_verified, "r") as f:
        retained = json.load(f)

    # Slug old should be pruned, new should remain
    retained_slugs = [item["slug"] for item in retained]
    assert slug_new in retained_slugs
    assert slug_old not in retained_slugs

    # Verify old file was deleted from local storage cache
    assert not (provider.get_file(slug_new).parent / "db_backup_old.sql.gz").exists()

    # Clean up test files
    if file_old.exists():
        file_old.unlink()
    if file_new.exists():
        file_new.unlink()
    provider.delete_file(slug_new)
    provider.delete_file(manifest_slug)
