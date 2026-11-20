#!/bin/bash
# Shared by open_gate_4k.command and open_gate_5.7k.command: runs the Windows kit's own tools with this folder's Python.
# macOS keeps its own mass-storage driver on the camera, and only root may take the camera over from it, so a live
# run goes through sudo. --dry-run and --selftest send nothing and run without it.
cd "$(dirname "$0")" || exit 1
PY="$PWD/.venv/bin/python"
APPLY="$PWD/../windows/tools/camera_tests/CT6_memory_read_check/open_gate_apply.py"
PRIVATE="$PWD/../windows/camera_private"
close() { echo; read -r -p "Press Return to close. "; exit "$1"; }
if [ ! -x "$PY" ]; then
  echo "Python environment missing: run setup.command first."
  close 1
fi
case " $* " in
  *" --dry-run "*|*" --selftest "*) "$PY" -I -B "$APPLY" "$@"; close $? ;;
esac
echo "macOS asks for your password: taking the camera over from its own USB driver needs admin rights."
# The sessions are saved as root; the same root shell gives them back to you afterwards, so a run longer than
# sudo's 5-minute grace period doesn't ask for the password a second time.
sudo /bin/bash -c 'private=$1; shift; "$@"; status=$?
  [ -d "$private" ] && chown -R "$SUDO_UID:$SUDO_GID" "$private"; exit $status' run "$PRIVATE" "$PY" -I -B "$APPLY" "$@"
close $?
