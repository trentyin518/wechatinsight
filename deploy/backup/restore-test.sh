#!/usr/bin/env bash
# Restore rehearsal for 8.2: restore a dump into a scratch database and verify
# row counts + migration head match production. Never point RESTORE_DATABASE_URL
# at production.
#
# Usage:
#   RESTORE_DATABASE_URL='postgresql://user:pass@host:5432/wechatinsight_restore' \
#     deploy/backup/restore-test.sh [path/to/wechatinsight-*.dump]
set -euo pipefail

ENV_FILE="${ENV_FILE:-/opt/wechat-insight/backend/.env}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/wechatinsight}"

DUMP="${1:-$(ls -1t "$BACKUP_DIR"/wechatinsight-*.dump 2>/dev/null | head -1 || true)}"
[[ -n "$DUMP" && -f "$DUMP" ]] || { echo "no dump found (arg or $BACKUP_DIR)" >&2; exit 2; }
: "${RESTORE_DATABASE_URL:?set RESTORE_DATABASE_URL to an empty scratch database}"

# Load KEY=VALUE without shell-evaluating the file (DSNs contain & and %).
while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%$'\r'}"
    [[ -z "$line" || "$line" == \#* ]] && continue
    export "$line"
done < "$ENV_FILE"
: "${DATABASE_URL:?DATABASE_URL is required}"

src="${DATABASE_URL/postgresql+psycopg2:/postgresql:}"
src="${src/postgresql+psycopg:/postgresql:}"
dst="${RESTORE_DATABASE_URL/postgresql+psycopg2:/postgresql:}"
dst="${dst/postgresql+psycopg:/postgresql:}"

if [[ "$(psql "$src" -Atc 'select current_database()')" == "$(psql "$dst" -Atc 'select current_database()')" ]]; then
    echo "refusing to restore into the source database" >&2
    exit 3
fi

echo "restoring $(basename "$DUMP") -> scratch db"
pg_restore --clean --if-exists --no-owner --no-privileges --dbname="$dst" "$DUMP"

status=0
for table in wechat_accounts wechat_articles article_metrics api_usage_logs; do
    s=$(psql "$src" -Atc "select count(*) from $table")
    d=$(psql "$dst" -Atc "select count(*) from $table")
    if [[ "$s" == "$d" ]]; then
        printf 'OK    %-16s src=%-8s dst=%s\n' "$table" "$s" "$d"
    else
        printf 'FAIL  %-16s src=%-8s dst=%s\n' "$table" "$s" "$d"
        status=1
    fi
done

s=$(psql "$src" -Atc 'select version_num from alembic_version')
d=$(psql "$dst" -Atc 'select version_num from alembic_version')
if [[ "$s" == "$d" ]]; then
    printf 'OK    %-16s %s\n' alembic_version "$s"
else
    printf 'FAIL  %-16s src=%s dst=%s\n' alembic_version "$s" "$d"
    status=1
fi

exit "$status"
