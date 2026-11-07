#!/usr/bin/env bash
# Daily logical backup of the production database.
# Cron:  15 3 * * *  /opt/wechat-insight/deploy/backup/pgdump-backup.sh >> /var/log/wechatinsight/backup.log 2>&1
set -euo pipefail

ENV_FILE="${ENV_FILE:-/opt/wechat-insight/backend/.env}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/wechatinsight}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

# Load KEY=VALUE without shell-evaluating the file (DSNs contain & and %).
while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    [[ -z "$line" || "$line" == \#* ]] && continue
    export "$line"
done < "$ENV_FILE"

: "${DATABASE_URL:?DATABASE_URL is required}"

# SQLAlchemy DSN -> libpq DSN understood by pg_dump (strip the +driver suffix).
LIBPQ_URL="${DATABASE_URL/postgresql+psycopg2:/postgresql:}"
LIBPQ_URL="${LIBPQ_URL/postgresql+psycopg:/postgresql:}"

mkdir -p "$BACKUP_DIR" /var/log/wechatinsight
STAMP="$(date -u +%Y%m%d-%H%M%S)"
OUT="$BACKUP_DIR/wechatinsight-$STAMP.dump"

pg_dump "$LIBPQ_URL" --format=custom --no-owner --no-privileges --file="$OUT"
pg_restore --list "$OUT" >/dev/null
sha256sum "$OUT" > "$OUT.sha256"

# Retention (local).
find "$BACKUP_DIR" -name 'wechatinsight-*.dump*' -type f -mtime "+$RETENTION_DAYS" -delete

# Offsite copy (optional): set AWS_S3_BUCKET in the environment file.
if [[ -n "${AWS_S3_BUCKET:-}" ]]; then
    aws s3 cp "$OUT" "s3://$AWS_S3_BUCKET/wechatinsight/$(basename "$OUT")"
    aws s3 cp "$OUT.sha256" "s3://$AWS_S3_BUCKET/wechatinsight/$(basename "$OUT").sha256"
fi

echo "backup ok: $OUT ($(du -h "$OUT" | cut -f1))"
