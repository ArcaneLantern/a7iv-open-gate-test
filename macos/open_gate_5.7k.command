#!/bin/bash
# 5.7K open gate for the Sony A7 IV (firmware 6.02): 5760x3840 at 300 Mbps (use a fast card; --rate100 for the menu's bit rate), rear screen 3:2 with focus frames, C3 de-squeeze cycle.
# Writes TEMPORARY settings into the camera's memory. A cold boot (battery out for 10 seconds) returns it to stock.
# Asks whether the camera is set to NTSC (24p) or PAL (25p, XAVC S 4K only). Extra options are passed on, e.g.  --ntsc  --pal  --dry-run  --selftest  --no-cycle  --no-lcd32  --old-lcd  --rate100
cd "$(dirname "$0")" || exit 1
exec "$PWD/run.sh" --real57 "$@"
