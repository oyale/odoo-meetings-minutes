#!/usr/bin/env bash
# Line coverage for community_meetings. Run inside the development container.
set -euo pipefail
DB="${ODOO_DB:-meeting_minutes}"
CONF="${ODOO_CONF:-/etc/odoo/odoo.conf}"
SRC="${ODOO_SRC:-/opt/meeting_addons/community_meetings}"
ODOO_USER="${ODOO_USER:-odoo}"
PY_BIN="${ODOO_PY:-/home/odoo/pyenv/versions/odoo/bin/python}"
TAGS="${1:-/community_meetings,-/community_meetings:TestMeetingRevisions}"
COV_FILE="${COVERAGE_FILE:-/tmp/coverage-community-meetings}"

for executable in systemctl sudo timeout "$PY_BIN"; do
    command -v "$executable" >/dev/null || { echo "Missing prerequisite: $executable" >&2; exit 1; }
done
[[ -f "$CONF" ]] || { echo "Odoo config not found: $CONF" >&2; exit 1; }
[[ -d "$SRC" ]] || { echo "Addon source not found: $SRC" >&2; exit 1; }

was_running=false
if systemctl is-active --quiet odoo; then
    was_running=true
fi

restore_service() {
    local result=$?
    trap - EXIT INT TERM
    if [[ "$was_running" == true ]]; then
        if ! systemctl start odoo; then
            echo "Failed to restart Odoo after coverage." >&2
            if (( result == 0 )); then result=1; fi
        elif ! systemctl is-active --quiet odoo; then
            echo "Odoo did not become active after coverage." >&2
            if (( result == 0 )); then result=1; fi
        fi
    fi
    exit "$result"
}
trap restore_service EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if [[ "$was_running" == true ]]; then
    systemctl stop odoo
    for _ in $(seq 1 30); do
        if ! systemctl is-active --quiet odoo; then break; fi
        sleep 1
    done
    if systemctl is-active --quiet odoo; then
        echo "Odoo is still active; refusing to run coverage against its database." >&2
        exit 1
    fi
fi

# The Odoo user must be able to revisit its initial directory when coverage exits.
cd /tmp
timeout -s INT -k 5 "${ODOO_TEST_TIMEOUT:-120}" sudo -u "$ODOO_USER" env COVERAGE_FILE="$COV_FILE" "$PY_BIN" -m coverage run \
    --source="$SRC" /opt/odoo/odoo-bin -c "$CONF" -d "$DB" -u community_meetings \
    --test-enable --stop-after-init --no-http --test-tags "$TAGS" --log-level=warn

sudo -u "$ODOO_USER" env COVERAGE_FILE="$COV_FILE" "$PY_BIN" -m coverage report -m \
    --omit="*/tests/*,*/migrations/*"
