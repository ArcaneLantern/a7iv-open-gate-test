#!/bin/bash
# 4K open gate for the Sony A7 IV (firmware 6.02): 3840x2560, rear screen 3:2, C3 de-squeeze cycle.
# Writes TEMPORARY settings into the camera's memory. A cold boot (battery out for 10 seconds) returns it to stock.
# Extra options are passed on, e.g.  --dry-run  --selftest  --no-cycle  --no-lcd32
cd "$(dirname "$0")" || exit 1
exec "$PWD/run.sh" "$@"
