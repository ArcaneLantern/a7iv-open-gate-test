@echo off
rem 5.7K open gate for the Sony A7 IV (firmware 6.02): 5760x3840, rear screen 3:2, C3 de-squeeze cycle.
rem Writes TEMPORARY settings into the camera's memory. A cold boot (battery out for 10 seconds) returns it to stock.
rem Asks whether the camera is set to NTSC (24p) or PAL (25p, XAVC S 4K only). Extra options are passed on, e.g.  --ntsc  --pal  --dry-run  --selftest  --no-cycle  --no-lcd32
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Python environment missing: run setup.cmd first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -I -B "tools\camera_tests\CT6_memory_read_check\open_gate_apply.py" --real57 %*
echo.
pause
