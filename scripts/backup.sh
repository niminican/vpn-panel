#!/bin/bash
# VPN Panel Backup Script
# Creates a backup of the database and WireGuard configs

set -e

BACKUP_DIR="/opt/vpn-panel/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/vpnpanel_backup_$TIMESTAMP.tar.gz"

mkdir -p "$BACKUP_DIR"

echo "Creating backup: $BACKUP_FILE"

tar -czf "$BACKUP_FILE" \
    -C /opt/vpn-panel data/ \
    -C /opt/vpn-panel .env \
    -C / etc/wireguard/ \
    2>/dev/null || true

# Keep only last 10 backups
ls -t "$BACKUP_DIR"/vpnpanel_backup_*.tar.gz 2>/dev/null | tail -n +11 | xargs -r rm

echo "Backup complete: $BACKUP_FILE"
echo "Size: $(du -h "$BACKUP_FILE" | cut -f1)"

# List recent backups
echo ""
echo "Recent backups:"
ls -lh "$BACKUP_DIR"/vpnpanel_backup_*.tar.gz 2>/dev/null | tail -5
