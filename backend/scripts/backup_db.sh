#!/usr/bin/env bash
# AuraMatch AI - DB backup
#
# Migrations (backend/app/db/migrations/) protect against "the schema needs
# to change" - they don't protect against operator error, a bad migration,
# or a disk problem. This is the other half of "irreplaceable data now
# exists": a plain pg_dump, no new infrastructure, run before any risky
# operation (a migration, a bulk re-ingestion) and on whatever schedule
# becomes appropriate once live data actually lands.
#
# Usage: backend/scripts/backup_db.sh [output_dir]   (default: backend/backups)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
OUT_DIR="${1:-$REPO_ROOT/backend/backups}"
mkdir -p "$OUT_DIR"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
OUT_FILE="$OUT_DIR/auramatch_${TIMESTAMP}.sql.gz"

echo "Dumping auramatch DB to $OUT_FILE ..."
docker compose -f "$REPO_ROOT/docker-compose.yml" exec -T db \
    pg_dump -U auramatch -d auramatch | gzip > "$OUT_FILE"

echo "Done: $(du -h "$OUT_FILE" | cut -f1) written."
echo "Restore with: gunzip -c $OUT_FILE | docker compose exec -T db psql -U auramatch -d auramatch"
