#!/usr/bin/env bash
# ===========================================================================
# WIDDX Nexus — Automated Backup Script
# ===========================================================================
# Usage:
#   bash deploy/backup.sh                   # Full backup
#   bash deploy/backup.sh --restore <file>  # Restore from backup
# ===========================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

BACKUP_DIR="${WIDDX_BACKUP_DIR:-./backups}"
WIDDX_DATA_DIR="${WIDDX_DATA_DIR:-./.widdx}"
RETENTION_DAYS="${WIDDX_BACKUP_RETENTION:-30}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/widdx_backup_$TIMESTAMP.tar.gz"

mkdir -p "$BACKUP_DIR"

echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  WIDDX Nexus — Backup Tool              ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"

case "${1:-backup}" in
    backup)
        echo -e "${YELLOW}→ Creating backup...${NC}"

        # ── Check data exists ──────────────────────────────
        if [[ ! -d "$WIDDX_DATA_DIR" ]]; then
            echo -e "${YELLOW}  ⚠ No .widdx directory found, skipping data backup${NC}"
            WIDDX_DATA_DIR=""
        fi

        # ── Create archive ─────────────────────────────────
        TAR_ARGS=""
        if [[ -n "$WIDDX_DATA_DIR" && -d "$WIDDX_DATA_DIR" ]]; then
            TAR_ARGS="$TAR_ARGS $WIDDX_DATA_DIR"
        fi
        # Also backup config.json if it exists
        if [[ -f "config.json" ]]; then
            TAR_ARGS="$TAR_ARGS config.json"
        fi

        if [[ -z "$TAR_ARGS" ]]; then
            echo -e "${RED}❌ Nothing to backup${NC}"
            exit 1
        fi

        tar -czf "$BACKUP_FILE" $TAR_ARGS 2>/dev/null
        BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
        echo -e "${GREEN}✅ Backup created: $BACKUP_FILE ($BACKUP_SIZE)${NC}"

        # ── Clean old backups ──────────────────────────────
        echo -e "${YELLOW}→ Cleaning backups older than $RETENTION_DAYS days...${NC}"
        find "$BACKUP_DIR" -name "widdx_backup_*.tar.gz" -mtime "+$RETENTION_DAYS" -delete 2>/dev/null
        echo -e "${GREEN}✅ Old backups cleaned${NC}"

        # ── Show backup list ───────────────────────────────
        echo ""
        echo -e "${YELLOW}Recent backups:${NC}"
        ls -lh "$BACKUP_DIR"/*.tar.gz 2>/dev/null | tail -5 || echo "  (none)"
        ;;

    restore)
        RESTORE_FILE="${2:-}"
        if [[ -z "$RESTORE_FILE" ]]; then
            echo -e "${RED}❌ Please specify backup file to restore${NC}"
            echo "  Usage: $0 --restore backups/widdx_backup_20260723_120000.tar.gz"
            exit 1
        fi
        if [[ ! -f "$RESTORE_FILE" ]]; then
            echo -e "${RED}❌ Backup file not found: $RESTORE_FILE${NC}"
            exit 1
        fi

        echo -e "${YELLOW}→ Restoring from $RESTORE_FILE...${NC}"
        echo -e "${RED}⚠ This will OVERWRITE existing files!${NC}"
        echo -n "Continue? (y/N): "
        read -r CONFIRM
        if [[ "$CONFIRM" != "y" && "$CONFIRM" != "Y" ]]; then
            echo "Cancelled."
            exit 0
        fi

        tar -xzf "$RESTORE_FILE"
        echo -e "${GREEN}✅ Restore completed${NC}"
        ;;

    list)
        echo -e "${YELLOW}Available backups:${NC}"
        ls -lh "$BACKUP_DIR"/*.tar.gz 2>/dev/null || echo "  (no backups found)"
        ;;

    cron)
        echo -e "${YELLOW}→ Installing cron job for daily backups...${NC}"
        SCRIPT_PATH="$(cd "$(dirname "$0")" && pwd)/backup.sh"
        CRON_JOB="0 2 * * * cd $(pwd) && bash $SCRIPT_PATH backup >> $BACKUP_DIR/backup.log 2>&1"
        (crontab -l 2>/dev/null | grep -v "backup.sh"; echo "$CRON_JOB") | crontab -
        echo -e "${GREEN}✅ Cron job installed (daily at 2 AM)${NC}"
        ;;

    *)
        echo "Usage: $0 {backup|restore|list|cron}"
        exit 1
        ;;
esac
