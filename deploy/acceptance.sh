#!/usr/bin/env bash
# 8.3 acceptance smoke test against the deployed stack.
# Verifies the checklist items that are observable over HTTP (plus DB checks
# when DATABASE_URL is provided). Read-only: never writes data.
#
#   API_BASE=https://api.wechatinsight.com \
#   FRONTEND_ORIGIN=https://www.wechatinsight.com \
#   SEARCH_Q='微信' \
#   DATABASE_URL='postgresql://...'      # optional, enables dedup/usage/null checks
#   deploy/acceptance.sh
set -uo pipefail

API_BASE="${API_BASE:-https://api.wechatinsight.com}"
FRONTEND_ORIGIN="${FRONTEND_ORIGIN:-https://www.wechatinsight.com}"
SEARCH_Q="${SEARCH_Q:-示例}"

fail=0
pass() { printf 'PASS  %s\n' "$*"; }
warn() { printf 'WARN  %s\n' "$*"; }
bad()  { printf 'FAIL  %s\n' "$*"; fail=1; }

# jget '<json>' '<python expr over d>'
jget() {
    python3 - "$1" "$2" <<'PY'
import json, sys
try:
    d = json.loads(sys.argv[1])
except Exception:
    print("")
    sys.exit(0)
try:
    print(eval(sys.argv[2], {}, {"d": d}))  # trusted local expressions only
except Exception:
    print("")
PY
}

req() { # req <path> -> sets CODE and BODY
    local out
    out="$(curl -sS -m 15 -H "Accept: application/json" -w $'\n%{http_code}' "$API_BASE$1" 2>/dev/null || true)"
    CODE="${out##*$'\n'}"
    BODY="${out%$'\n'*}"
}

account_id=""
article_id=""

echo "== API_BASE=$API_BASE  SEARCH_Q=$SEARCH_Q =="

# 1. health
req /health
if [[ "$CODE" == "200" && "$(jget "$BODY" 'd.get("status")')" == "ok" ]]; then
    pass "GET /health -> 200 {status: ok}"
else
    bad "GET /health -> $CODE $BODY"
fi

# 2. search + local total + pagination
q_enc="$(python3 -c 'import sys,urllib.parse;print(urllib.parse.quote(sys.argv[1]))' "$SEARCH_Q")"
req "/api/v1/accounts?q=$q_enc&page=1&page_size=5"
total="$(jget "$BODY" 'd.get("total")')"
count="$(jget "$BODY" 'len(d.get("items", []))')"
if [[ "$CODE" == "200" && -n "$total" && -n "$count" ]]; then
    if [[ "$count" -le 5 && "$total" -ge "$count" ]]; then
        pass "search total=$total items=$count (page_size enforced)"
    else
        bad "search total=$total items=$count (pagination broken)"
    fi
    account_id="$(jget "$BODY" 'd["items"][0]["id"] if d.get("items") else ""')"
else
    bad "GET /api/v1/accounts -> $CODE $BODY"
fi

if [[ -z "$account_id" ]]; then
    warn "no account matched '$SEARCH_Q'; skipping detail checks (set SEARCH_Q to seeded data)"
else
    req "/api/v1/accounts/$account_id"
    if [[ "$CODE" == "200" && -n "$(jget "$BODY" 'd.get("name")')" ]]; then
        pass "account detail id=$account_id"
    else
        bad "account detail id=$account_id -> $CODE $BODY"
    fi

    req "/api/v1/accounts/$account_id/articles?page=1&page_size=5"
    if [[ "$CODE" == "200" ]]; then
        pass "article list total=$(jget "$BODY" 'd.get("total")')"
        article_id="$(jget "$BODY" 'd["items"][0]["id"] if d.get("items") else ""')"
    else
        bad "article list -> $CODE $BODY"
    fi

    if [[ -n "$article_id" ]]; then
        req "/api/v1/articles/$article_id"
        if [[ "$CODE" == "200" ]]; then
            pass "article detail id=$article_id (metrics null=$(jget "$BODY" 'd.get("metrics") is None'))"
        else
            bad "article detail id=$article_id -> $CODE $BODY"
        fi

        req "/api/v1/articles/$article_id/metrics"
        if [[ "$CODE" == "200" ]]; then
            pass "metrics history points=$(jget "$BODY" 'len(d.get("points", []))')"
        else
            bad "metrics history -> $CODE $BODY"
        fi
    fi
fi

# 3. unified error envelope
req /api/v1/accounts/999999999
if [[ "$CODE" == "404" && "$(jget "$BODY" 'd.get("error", {}).get("code")')" == "NOT_FOUND" ]]; then
    pass "404 envelope {error:{code,message}}"
else
    bad "404 envelope -> $CODE $BODY"
fi

# 4. CORS allows the production origin exactly
origin="$(curl -sS -m 15 -D - -o /dev/null -H "Origin: $FRONTEND_ORIGIN" "$API_BASE/health" 2>/dev/null \
    | tr -d '\r' | awk -F': ' 'tolower($1)=="access-control-allow-origin"{print $2}')"
if [[ "$origin" == "$FRONTEND_ORIGIN" ]]; then
    pass "CORS allows $FRONTEND_ORIGIN"
else
    bad "CORS header for $FRONTEND_ORIGIN is '$origin' (fix CORS_ORIGINS)"
fi

# 5. DB-level checks: dedup, usage logs, and null-not-zero
if [[ -z "${DATABASE_URL:-}" ]]; then
    warn "DATABASE_URL not set; skipped dedup/cost/null checks"
elif ! command -v psql >/dev/null 2>&1; then
    warn "psql not installed; skipped dedup/cost/null checks"
else
    dsn="${DATABASE_URL/postgresql+psycopg2:/postgresql:}"
    dsn="${dsn/postgresql+psycopg:/postgresql:}"

    dup_acc="$(psql "$dsn" -Atc 'select count(*) from (select provider, provider_account_id from wechat_accounts group by 1,2 having count(*)>1) x' 2>/dev/null)"
    dup_art="$(psql "$dsn" -Atc 'select count(*) from (select provider, normalized_url from wechat_articles group by 1,2 having count(*)>1) x' 2>/dev/null)"
    usage="$(psql "$dsn" -Atc 'select count(*) from api_usage_logs' 2>/dev/null)"

    if [[ "$dup_acc" == "0" ]]; then pass "no duplicate accounts"
    elif [[ -n "$dup_acc" ]]; then bad "duplicate accounts: $dup_acc"
    else warn "duplicate-account query failed (check DATABASE_URL/psql access)"; fi

    if [[ "$dup_art" == "0" ]]; then pass "no duplicate articles"
    elif [[ -n "$dup_art" ]]; then bad "duplicate articles: $dup_art"
    else warn "duplicate-article query failed (check DATABASE_URL/psql access)"; fi

    if [[ -n "$usage" && "$usage" -gt 0 ]]; then
        pass "api_usage_logs recorded: $usage rows"
    else
        warn "api_usage_logs empty (${usage:-n/a}) — expected while DEFAULT_PROVIDER=mock"
    fi

    # Ground-truth "missing metric is null, not 0": an article with no snapshot
    # row must render metrics=null through the API.
    if [[ -n "$article_id" ]]; then
        snap="$(psql "$dsn" -Atc "select count(*) from article_metrics where article_id = $article_id" 2>/dev/null)"
        if [[ "$snap" == "0" ]]; then
            req "/api/v1/articles/$article_id"
            [[ "$(jget "$BODY" 'd.get("metrics") is None')" == "True" ]] \
                && pass "article $article_id has no snapshot -> API metrics=null" \
                || bad "article $article_id has no snapshot but API returned a metric object"
        fi
    fi
fi

echo
if [[ "$fail" -eq 0 ]]; then echo "RESULT: PASS"; else echo "RESULT: FAIL"; exit 1; fi
