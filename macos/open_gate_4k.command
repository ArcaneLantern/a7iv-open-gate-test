#!/bin/bash
# 4K open gate for the Sony A7 IV (firmware 6.02): 3840x2560, file headers 3840x2560 (no remux needed), rear screen 3:2 with focus frames, C3 de-squeeze cycle 3:2 / 2:1 / 2.25:1 / 2.4:1.
# Writes TEMPORARY settings into the camera's memory. A cold boot (battery out for 10 seconds) returns it to stock.
# Asks whether the camera is set to NTSC (24p) or PAL (25p, XAVC S 4K only). Extra options are passed on, e.g.  --ntsc  --pal  --dry-run  --selftest  --no-cycle  --no-lcd32  --old-lcd  --no-meta
# Cold boot with the battery out before running, and set Proxy Recording to Off.
cd "$(dirname "$0")" || exit 1
exec "$PWD/run.sh" "$@"
