#!/usr/bin/env bash
# Rerun the Tepi checks from this checkout. Does not open the real progress log.
set -u
ROOT="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
cd "$ROOT" || exit 1
fail=0

pass() { printf '%s: PASS\n' "$1"; }
fail_tool() { printf '%s: FAIL\n' "$1"; fail=1; }

real_db="${HOME}/.local/share/tepi/tepi.sqlite"
real_before=""
if [[ -f "$real_db" ]]; then
  real_before="$(stat -c '%y %s' "$real_db")"
fi

if python3 -m unittest discover -s tests; then
  pass tests
else
  fail_tool tests
fi

if command -v ruff >/dev/null 2>&1; then
  if ruff check --no-cache --config "$ROOT/ruff.toml" tepi tests; then
    pass ruff
  else
    fail_tool ruff
  fi
else
  printf '%s\n' "ruff: SKIPPED (not installed)"
  fail=1
fi

if command -v shellcheck >/dev/null 2>&1; then
  if shellcheck -f gcc bin/tepi verify.sh; then
    pass shellcheck
  else
    fail_tool shellcheck
  fi
else
  printf '%s\n' "shellcheck: SKIPPED (not installed)"
  fail=1
fi

if command -v codespell >/dev/null 2>&1; then
  if codespell -I "$ROOT/.codespell-ignore" \
    README.md AGENTS.md bin/tepi verify.sh tepi tests _handoff/reports; then
    pass codespell
  else
    fail_tool codespell
  fi
else
  printf '%s\n' "codespell: SKIPPED (not installed)"
  fail=1
fi

if command -v gitleaks >/dev/null 2>&1; then
  leak_log="$(mktemp)"
  git_ok=0
  dir_ok=0
  if gitleaks git --no-banner --redact . >"$leak_log" 2>&1; then
    git_ok=1
  fi
  if gitleaks dir --no-banner --redact . >>"$leak_log" 2>&1; then
    dir_ok=1
  fi
  if [[ "$git_ok" -eq 1 && "$dir_ok" -eq 1 ]]; then
    pass gitleaks
  else
    fail_tool gitleaks
    cat "$leak_log"
  fi
  rm -f "$leak_log"
else
  printf '%s\n' "gitleaks: SKIPPED (not installed)"
  fail=1
fi

if [[ -n "$real_before" ]]; then
  real_after="$(stat -c '%y %s' "$real_db")"
  if [[ "$real_before" == "$real_after" ]]; then
    pass "real-db untouched"
  else
    fail_tool "real-db untouched"
  fi
fi

exit "$fail"
