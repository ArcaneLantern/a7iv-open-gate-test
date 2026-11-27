@echo off
rem 5.7K open gate for the Sony A7 IV (firmware 6.02): 5760x3840 at 300 Mbps (use a fast card; --rate100 for the menu's bit rate), no B pictures (no duplicate frames), file headers 5760x3840 (no remux needed; no in-camera playback), rear screen 3:2 with focus frames, C3 de-squeeze cycle 3:2 / 2:1 / 2.25:1 / 2.4:1.
rem Writes TEMPORARY settings into the camera's memory. A cold boot (battery out for 10 seconds) returns it to stock.
rem Asks whether the camera is set to NTSC (24p) or PAL (25p, XAVC S 4K only), and whether to switch the camera's noise reduction off.
rem Extra options are passed on, e.g.  --ntsc  --pal  --nr-off  --nr-on  --dry-run  --selftest  --no-cycle  --no-lcd32  --old-lcd  --no-meta  --rate100
rem Cold boot with the battery out before running, and set Proxy Recording to Off.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Python environment missing: run setup.cmd first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -I -B "tools\camera_tests\CT6_memory_read_check\open_gate_apply.py" --real57 %*
echo.
pause
