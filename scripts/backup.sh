#!/bin/bash
# VPN Panel - Database Backup Script
#
# Usage:
#   ./scripts/backup.sh                    # Backup to default location
#   ./scripts/backup.sh /custom/backup/dir # Backup to custom directory
#
# Recommended cron: Run daily at 2:00 AM
#   0 2 * * * /opt/vpn-panel/scripts/backup.sh >> /var/log/vpn-panel-backup.log 2>&1

set -euo pipefail

BACKUP_DIR="${1:-/opt/vpn-panel/backups}"
DB_PATH="${DB_PATH:-/opt/vpn-panel/data/vpnpanel.db}"
WG_CONFIG_DIR="${WG_CONFIG_DIR:-/etc/wireguard}"
RETENTION_COUNT=30
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="vpnpanel_backup_${TIMESTAMP}"

echo "=== VPN Panel Backup - $(date) ==="

mkdir -p "${BACKUP_DIR}"

# Create temp directory
TEMP_DIR=$(mktemp -d)
trap 'rm -rf "${TEMP_DIR}"' EXIT

WORK="${TEMP_DIR}/${BACKUP_NAME}"
mkdir -p "${WORK}"

# 1. Backup SQLite database using online backup (safe while DB is in use)
if [ -f "${DB_PATH}" ]; then
    echo "[1/3] Backing up database..."
    if command -v sqlite3 &>/dev/null; then
        sqlite3 "${DB_PATH}" ".backup '${WORK}/vpnpanel.db'"
    else
        cp "${DB_PATH}" "${WORK}/vpnpanel.db"
        # Also copy WAL/SHM if present
        [ -f "${DB_PATH}-wal" ] && cp "${DB_PATH}-wal" "${WORK}/vpnpanel.db-wal"
        [ -f "${DB_PATH}-shm" ] && cp "${DB_PATH}-shm" "${WORK}/vpnpanel.db-shm"
    fi
    echo "  Database: $(du -h "${WORK}/vpnpanel.db" | cut -f1)"
else
    echo "[1/3] WARNING: Database not found at ${DB_PATH}"
fi

# 2. Backup WireGuard configs and .env
echo "[2/3] Backing up configs..."
[ -d "${WG_CONFIG_DIR}" ] && cp -r "${WG_CONFIG_DIR}" "${WORK}/wireguard" 2>/dev/null || true
[ -f "/opt/vpn-panel/.env" ] && cp "/opt/vpn-panel/.env" "${WORK}/.env" 2>/dev/null || true

# 3. Create compressed archive
echo "[3/3] Creating archive..."
cd "${TEMP_DIR}"
tar -czf "${BACKUP_DIR}/${BACKUP_NAME}.tar.gz" "${BACKUP_NAME}"
BACKUP_SIZE=$(du -h "${BACKUP_DIR}/${BACKUP_NAME}.tar.gz" | cut -f1)

# Cleanup old backups (keep last N)
ls -t "${BACKUP_DIR}"/vpnpanel_backup_*.tar.gz 2>/dev/null | tail -n +$((RETENTION_COUNT + 1)) | xargs -r rm

TOTAL=$(ls "${BACKUP_DIR}"/vpnpanel_backup_*.tar.gz 2>/dev/null | wc -l)
echo "=== Done: ${BACKUP_DIR}/${BACKUP_NAME}.tar.gz (${BACKUP_SIZE}) | ${TOTAL} backups kept ==="
