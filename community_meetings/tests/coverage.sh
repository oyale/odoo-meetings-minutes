#!/usr/bin/env bash
# Line coverage for community_meetings, measured by running its Odoo test suite.
# Run INSIDE the Odoo container as a user with sudo.
#
# One-time prerequisite:
#   /home/odoo/pyenv/versions/odoo/bin/pip install coverage
#
# Usage:
#   bash coverage.sh                 # core suite (revisions excluded: need HTTP)
#   ODOO_DB=other bash coverage.sh
#   bash coverage.sh /community_meetings:TestProposalConvergence
set -euo pipefail
DB="${ODOO_DB:-meeting_minutes}"
CONF="${ODOO_CONF:-/etc/odoo/odoo.conf}"
SRC="${ODOO_SRC:-/opt/meeting_addons/community_meetings}"
ODOO_USER="${ODOO_USER:-odoo}"
PY_BIN="${ODOO_PY:-/home/odoo/pyenv/versions/odoo/bin/python}"
TAGS="${1:-/community_meetings,-/community_meetings:TestMeetingRevisions}"
COV_FILE="/tmp/coverage-community-meetings"

systemctl stop odoo 2>/dev/null || true
for _ in $(seq 1 30); do systemctl is-active --quiet odoo || break; sleep 1; done

sudo -u "$ODOO_USER" env COVERAGE_FILE="$COV_FILE" "$PY_BIN" -m coverage run \
    --source="$SRC" /opt/odoo/odoo-bin -c "$CONF" -d "$DB" -u community_meetings \
    --test-enable --stop-after-init --no-http --test-tags "$TAGS" --log-level=warn

systemctl start odoo 2>/dev/null || true

sudo -u "$ODOO_USER" env COVERAGE_FILE="$COV_FILE" "$PY_BIN" -m coverage report -m \
    --omit="*/tests/*,*/migrations/*"
