#!/usr/bin/env bash
# Isolated service/coverage failure-path checks; never touches the real service.
set -euo pipefail
here="$(cd -- "$(dirname "$0")" >/dev/null && pwd -P)"
sandbox="$(mktemp -d)"
trap 'rm -rf "$sandbox"' EXIT
mkdir -p "$sandbox/bin" "$sandbox/src"
touch "$sandbox/odoo.conf"
cat > "$sandbox/bin/systemctl" <<'SH'
#!/usr/bin/env bash
case "$1" in
    is-active) [[ "$(cat "$RUNNER_STATE")" == active ]] ;;
    stop)
        [[ "${FAIL_STOP:-0}" != 1 ]] || exit 12
        [[ "${STICKY_ACTIVE:-0}" != 1 ]] && printf inactive > "$RUNNER_STATE"
        ;;
    start)
        [[ "${FAIL_START:-0}" != 1 ]] || exit 13
        printf active > "$RUNNER_STATE"
        ;;
esac
SH
cat > "$sandbox/bin/sudo" <<'SH'
#!/usr/bin/env bash
case " $* " in
    *' coverage run '*)
        [[ "${SEND_TERM:-0}" != 1 ]] || { kill -TERM "$PPID"; sleep 1; }
        [[ "${FAIL_TEST:-0}" != 1 ]] ;;
    *' coverage report '*) [[ "${FAIL_REPORT:-0}" != 1 ]] ;;
esac
SH
cat > "$sandbox/bin/odoo-python" <<'SH'
#!/usr/bin/env bash
exit 0
SH
chmod +x "$sandbox/bin/"*
export PATH="$sandbox/bin:$PATH" RUNNER_STATE="$sandbox/service-state"
export ODOO_CONF="$sandbox/odoo.conf" ODOO_SRC="$sandbox/src" ODOO_PY="$sandbox/bin/odoo-python"
run_case() {
    local name="$1" initial="$2" expected_status="$3" expected_state="$4"
    shift 4
    printf '%s' "$initial" > "$RUNNER_STATE"
    local result=0
    env "$@" bash "$here/coverage.sh" > "$sandbox/out" 2>&1 || result=$?
    if [[ "$expected_status" == ok && "$result" != 0 ]] ||
       [[ "$expected_status" == fail && "$result" == 0 ]] ||
       [[ "$(cat "$RUNNER_STATE")" != "$expected_state" ]]; then
        echo "Coverage runner case failed: $name (status=$result, state=$(cat "$RUNNER_STATE"))" >&2
        cat "$sandbox/out" >&2
        exit 1
    fi
}
run_case success active ok active
run_case initially_stopped inactive ok inactive
run_case stop_failure active fail active FAIL_STOP=1
run_case stop_timeout active fail active STICKY_ACTIVE=1
run_case test_failure active fail active FAIL_TEST=1
run_case report_failure active fail active FAIL_REPORT=1
run_case restart_failure active fail inactive FAIL_START=1
run_case term_signal active fail active SEND_TERM=1
printf 'Coverage runner failure-path checks passed.\n'
