#!/usr/bin/env bash
# Daily logical backup of the production database.
# Cron:  15 3 * * *  /opt/wechat-insight/deploy/backup/pgdump-backup.sh >> /var/log/wechatinsight/backup.log 2>&1
set -euo pipefail

ENV_FILE="${ENV_FILE:-/opt/wechat-insight/backend/.env}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/wechatinsight}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

# cron runs with a minimal PATH; prefer a client that is at least as new as the
# server (Neon is on PG 18, so the distro's pg_dump 13 would abort).
for _pgbin in /usr/pgsql-18/bin /opt/pg18/usr/pgsql-18/bin; do
    if [[ -x "$_pgbin/pg_dump" ]]; then
        export PATH="$_pgbin:$PATH"
        [[ -d "$_pgbin/../lib" ]] && export LD_LIBRARY_PATH="$_pgbin/../lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
        break
    fi
done

# Load KEY=VALUE without shell-evaluating the file (DSNs contain & and %).
while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    [[ -z "$line" || "$line" == \#* ]] && continue
    export "$line"
done < "$ENV_FILE"

: "${DATABASE_URL:?DATABASE_URL is required}"

# Neon pooler needs the endpoint option when libpq lacks SNI support.
_url="${DIRECT_DATABASE_URL:-$DATABASE_URL}"
LIBPQ_URL="${_url/postgresql+psycopg2:/postgresql:}"
LIBPQ_URL="${LIBPQ_URL/postgresql+psycopg:/postgresql:}"

mkdir -p "$BACKUP_DIR" /var/log/wechatinsight
STAMP="$(date -u +%Y%m%d-%H%M%S)"
OUT="$BACKUP_DIR/wechatinsight-$STAMP.dump"

pg_dump "$LIBPQ_URL" --format=custom --no-owner --no-privileges --file="$OUT.tmp"
[[ -s "$OUT.tmp" ]] || { rm -f "$OUT.tmp"; echo "empty dump, aborting" >&2; exit 1; }
pg_restore --list "$OUT.tmp" >/dev/null
mv "$OUT.tmp" "$OUT"
sha256sum "$OUT" > "$OUT.sha256"

# Retention (local).
find "$BACKUP_DIR" -name 'wechatinsight-*.dump*' -type f -mtime "+$RETENTION_DAYS" -delete

# Offsite copy (optional): set AWS_S3_BUCKET in the environment file.
if [[ -n "${AWS_S3_BUCKET:-}" ]]; then
    aws s3 cp "$OUT" "s3://$AWS_S3_BUCKET/wechatinsight/$(basename "$OUT")"
    aws s3 cp "$OUT.sha256" "s3://$AWS_S3_BUCKET/wechatinsight/$(basename "$OUT").sha256"
fi

echo "backup ok: $OUT ($(du -h "$OUT" | cut -f1))"
