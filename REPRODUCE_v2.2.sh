#!/usr/bin/env bash
# REPRODUCE v2.2 — compatibility alias for REPRODUCE_v2.5.sh.
# The v2.2 report and the v2.5 report share the same reproduction pipeline, so this
# script simply defers to REPRODUCE_v2.5.sh to avoid path/setup drift.
set -e
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/REPRODUCE_v2.5.sh" "$@"