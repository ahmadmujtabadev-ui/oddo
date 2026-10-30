#!/usr/bin/env bash
# Install the addon into a fresh database and run its test suite.
#
# odoo exits 0 even when a module fails to load or a test errors in some
# paths, so the log is also scanned for ERROR/CRITICAL and the run fails on
# any hit.
set -euo pipefail

MODULE="${MODULE:-my_module}"
DB_NAME="${DB_NAME:-ci_test}"
LOG=/tmp/odoo-ci.log

echo "Module:   $MODULE"
echo "Database: $DB_NAME"
echo

# "/<module>" keeps the suite to this addon's own tests instead of running
# Odoo's full core suite.
odoo \
    --db_host="${DB_HOST:-db}" \
    --db_port="${DB_PORT:-5432}" \
    --db_user="${DB_USER:-odoo}" \
    --db_password="${DB_PASSWORD:-odoo}" \
    --database="$DB_NAME" \
    --init="$MODULE" \
    --without-demo=all \
    --test-enable \
    --test-tags="/$MODULE" \
    --log-level=info \
    --stop-after-init \
    2>&1 | tee "$LOG"

# IGNORE_PATTERN lets a known-benign line through, e.g.
#   IGNORE_PATTERN='unable to send email'
FILTER="${IGNORE_PATTERN:-}"
if [ -n "$FILTER" ]; then
    FOUND=$(grep -E ' (ERROR|CRITICAL) ' "$LOG" | grep -vE "$FILTER" || true)
else
    FOUND=$(grep -E ' (ERROR|CRITICAL) ' "$LOG" || true)
fi

if [ -n "$FOUND" ]; then
    echo
    echo "FAILED: Odoo logged errors during install/test:"
    echo "$FOUND"
    exit 1
fi

echo
echo "OK: $MODULE installed and all tests passed."
