"""Apply an open-gate state to a Sony A7 IV (firmware 6.02) for this power-on: 4K (3840x2560) or, with --real57,
5.7K (5760x3840), each with the rear screen at 3:2 and the C3 de-squeeze preview cycle.

Temporary: memory only. A cold boot (battery out for 10 seconds) returns the camera to stock.
Run it through open_gate_4k.cmd or open_gate_5.7k.cmd, or on macOS through macos/open_gate_4k.command or
macos/open_gate_5.7k.command.
It asks whether the camera is set to NTSC (24p) or PAL (25p, XAVC S 4K only); step 2 differs between the two.

    --ntsc / --pal   answer that question on the command line
    --no-cycle   leave out the C3 cycle        --no-lcd32   leave out the rear screen 3:2 and the C3 cycle
    --old-lcd    the rear-screen steps as before 2026-11-21 (no focus frames on the rear screen)
    --rate100    5.7K: the menu's own bit rate (at most 100 Mbps) instead of 300 Mbps on the 100M record settings
    --dry-run    show what would be sent       --selftest   each step's self-test on a simulated camera
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAP = HERE.parents[1]
RUNNER = HERE / "ct6_level1_run.py"
LISTER = MAP / "camera_tests" / "CT1_usb_first_contact" / "ct1_stage2_service.py"
PRIVATE = MAP.parent / "camera_private"
FIRMWARE = "6.02"
# level, design, SHA-256 of the pinned library (the runner refuses any other), where the runner puts the outcome, what the step is
BASE = [
    (13, "dmmwb4688_v1", "938f9baf7d9d77a4163cc3568341614e1023dea1a4c4210bc85975ae437a6009", "level1314", "the raw write buffer made taller"),
    (5, "ogsq_v3", "527c12d151824a5431dafc46693033ea53add09b96dd59e39aa975139e454446", "level56", "the full-height picture, every sensor row"),
]
PIC_57N = (5, "og57n_v1", "2ad88f667330657007d7666a0d88c651d77a7d9f6487b39c88640e85aac1f7b4", "level56", "the full-height picture, 5760x3840 out of the first scaler, the firmware's own column geometry")
OUT_2560 = (16, "outsz2560_v1", "af755e0b5dc17586565947f49cc4be839d1cdef6dfd2db739b9123db53ab59d7", "level1617", "the output size 3840x2560")
ENC_HS_S = (19, "ogfile2560_hs_s_v1", "7a354f584b36bc38309f8257cd04784c6d245d3de2ae8e4a96a7b3ca0a21a7a2", "level1920", "the encoder side for XAVC HS 4K and XAVC S 4K")
OUT_57 = (16, "og57cp_v3", "eb14cbfff320dd8b23e5fd70326a115fc23350029e7dbe187b9979301dd6d599", "level1617",
          "four scaler units, a buffer for the output picture (30.8 MB units) and its id in the size table, the output size 5760x3840")
LCD_32 = (16, "lcdfill_v2", "1393e38434ac21b2f1050cde5534fb06feed459bd9c837e0d5d69a0a0bd2f22c", "level1617",
          "the rear screen at 3:2 with the focus frames: the squeezed live view stretched over the whole 3:2 panel (F791), and the frame "
          "tables set to that rectangle (v2; works on the camera, F968)")
CYCLE = (19, "lcdcycle_v6", "64a67f1f7d541e9946e1084a382884d11b11f17031cc29a746e18e0d1b58fe10", "level1920",
         "the C3 key steps the rear-screen preview 3:2 -> 2:1 -> 2.4:1 in movie mode and keeps the focus frames (appFw code; v6 = v5, which "
         "works on the camera, F858, plus the frame tables; works on the camera in 3:2, F968)")
# The steps as they were before 2026-11-21 (no focus frames on the rear screen, F966): --old-lcd puts them back in place of the two above.
LCD_32_V1 = (16, "lcdfill_v1", "1141376a1dd43614a6b9950fd89b7449d292adceaecc254a4561a1f18c4cb57d", "level1617",
             "the rear screen at 3:2: the squeezed live view stretched over the whole 3:2 panel (F791; no focus frames, F966)")
CYCLE_V5 = (19, "lcdcycle_v5", "590a450de873e70bce6b5a7414183aa46892e71e2afa5ac6b54055380c5d728c", "level1920",
            "the C3 key steps the rear-screen preview 3:2 -> 2:1 -> 2.4:1 in movie mode (appFw code; v5, works on the camera, F858; no focus frames, F966)")
ENC_57 = (19, "ogfile57_v1", "aa1f318fafe1a71a5286b076c2f4fc274f68f196aeaf9bf8518b4841dd2c5f8a", "level1920",
          "the encoder side for 5760x3840: both cores, memory, XAVC HS 4K and XAVC S 4K")
# 2026-11-21, a test the owner asked for: ENC_57 with the 100M record settings at 300 Mbps (build/build_og57.py --rate300; the rate figures and
# the level of Sony's own dormant 5760x3240 profiles). Works on the camera and the blocking seen at 100 Mbps is gone (F971): step 4 of the
# 5.7K state since 2026-11-21. ENC_57 is what --rate100 puts back.
ENC_57_300 = (19, "ogfile57r300_v1", "56f4af121f1b944fb50e94924035af3212b4e041ee3393e39d20d90a08693c75", "level1920",
              "the encoder side for 5760x3840 with the 100M record settings at 300 Mbps: both cores, memory, XAVC HS 4K and XAVC S 4K")
# 2026-11-21: step 2 for a camera set to PAL: the same design moved to drive mode 0x880, which PAL uses for full-frame 4K 25p, with the
# stored record of that mode in the PAL family's bytes (build/build_mode880.py). Keyed by the NTSC design's name. A state whose step 2
# is not here has no PAL build. Both applied and worked on the camera on 2026-11-21 (F965).
PAL_SQ = (5, "ogsq880_v1", "f7db0d936713a2a41acdfc7746828ea7d0a201b32fc58a166529bbf519620636", "level56",
          "the full-height picture, every sensor row, in drive mode 0x880 (camera set to PAL, 25p)")
PAL_57N = (5, "og57n880_v1", "e2908a73cecab247d5d37be5d757beeb9a1c30fcf60f55aa0a481b93af527760", "level56",
           "the full-height picture, 5760x3840 out of the first scaler, in drive mode 0x880 (camera set to PAL, 25p)")
PAL = {"ogsq_v3": PAL_SQ, "og57n_v1": PAL_57N}
RATE = {"NTSC": "24p", "PAL": "25p"}
BOTH = "XAVC HS 4K or XAVC S 4K"
STATES = {
    "default": {"steps": BASE + [OUT_2560, ENC_HS_S, LCD_32, CYCLE], "formats": BOTH, "size": "3840x2560", "test": None,
                "title": "Open gate for the Sony A7 IV: a 3840x2560 recording of the whole 3:2 sensor area",
                "notes": ["The rear screen shows the whole picture at 3:2 while shooting (step 5); every 16:9 picture on the rear screen fills it too. The file is",
                          "3840x2560 and plays back in the camera at 3:2."]},
    "real57": {"steps": BASE[:1] + [PIC_57N, OUT_57, ENC_57_300, LCD_32, CYCLE], "formats": "XAVC HS 4K", "size": "5760x3840", "test": None,
               "title": "Open gate for the Sony A7 IV: a real 5760x3840 recording of the whole 3:2 sensor area",
               "notes": ["The file is 5760x3840 with real detail: the first scaler gives 5760x3840 and nothing is enlarged (F906). Its container",
                         "header says 3840x2160; the picture inside is 5760x3840.",
                         "The record settings marked 100M record at about 300 Mbps (peaks to 340): at 100 Mbps this size showed blocking (F971).",
                         "The lower record settings keep their own bit rate. The menu and the remaining time still say 100M: the card fills",
                         "three times as fast as shown. Use a fast card (about 40 MB a second: CFexpress Type A, or SD V60 / V90).",
                         "--rate100 gives the earlier step 4, with the menu's own bit rate.",
                         "Not yet tried in this state: long recordings (heat).",
                         "IF THE CAMERA RESTARTS OR FREEZES: do not cold boot; connect USB and say so (level 10 reads the crash report)."]},
}
COLD_BOOT = "Cold boot the camera (power off, battery out for 10 seconds). That returns it to stock."


def say(text=""):
    print(text, flush=True)


def for_family(steps, family):
    """The steps for a camera set to NTSC (as they are) or PAL (step 2 replaced by its PAL library)."""
    if family != "PAL":
        return steps
    out = []
    for step in steps:
        if step[0] == 5:
            if step[1] not in PAL:
                raise SystemExit("This state has no PAL build (its step 2 is %s). Set the camera's NTSC/PAL Selector to NTSC for it. Nothing was sent." % step[1])
            step = PAL[step[1]]
        out.append(step)
    return out


def ask_family():
    say("Is the camera set to NTSC or PAL? (Menu > Setup > Area/Date > NTSC/PAL Selector. NTSC offers 24p/30p/60p, PAL offers 25p/50p.)")
    answer = input("Type NTSC or PAL: ").strip().upper()
    if answer not in RATE:
        raise SystemExit("Neither NTSC nor PAL. Nothing was sent.")
    return answer


def library(level, design):
    return HERE / "helper" / ("libJit_level%d_%s.so" % (level, design))


def check_libraries(steps):
    """Every pinned library is on this PC and is the file whose hash is written above."""
    for level, design, sha, _, _ in steps:
        path = library(level, design)
        if not path.is_file():
            raise SystemExit("STOP: %s is missing. Nothing was sent." % path)
        got = hashlib.sha256(path.read_bytes()).hexdigest()
        if got != sha:
            raise SystemExit("STOP: %s is not the pinned file (SHA-256 %s). Nothing was sent." % (path.name, got))


def usb_state():
    """What Windows and libusb show now: 'drive' (Mass Storage, ready), 'service', or 'other'. Listing only; nothing is sent."""
    r = subprocess.run([sys.executable, "-I", "-B", str(LISTER), "--list"], capture_output=True, text=True, encoding="utf8", errors="replace", cwd=str(MAP))
    m = re.search(r"libusb sees: (\d+) Sony mass-storage device\(s\).*?, (\d+) Sony service device\(s\)", r.stdout)
    if not m:
        return "other"
    return "drive" if int(m.group(1)) == 1 and int(m.group(2)) == 0 else "service" if int(m.group(2)) else "other"


def wait_for_drive(first, timeout=600):
    """Wait until the camera shows as a USB drive. Returns False if it does not within `timeout` seconds."""
    asked = False
    end = time.time() + timeout
    while True:
        if usb_state() == "drive":
            return True
        if not asked:
            say()
            if first:
                say("The camera is not showing as a USB drive (Mass Storage).")
                say("  Turn it on, dial on stills, and connect the USB cable. USB Connection Mode: Mass Storage.")
            else:
                say(">>> Unplug the USB cable from the camera and plug it in again.")
                say(">>> Do NOT power the camera off: that would undo the steps already done.")
            say("Waiting for the camera (Ctrl+C to stop) ...")
            asked = True
        if time.time() > end:
            return False
        time.sleep(2)


def last_result_sha():
    """The SHA-256 of the result the newest saved session fetched, if any. The runner deletes a result file left on the camera's RAM disk
    only when its content has this hash; when there is none on the camera this does nothing."""
    if not PRIVATE.is_dir():
        return None
    for folder in sorted((p for p in PRIVATE.iterdir() if p.is_dir() and p.name.startswith("CT6_")), reverse=True):
        try:
            man = json.loads((folder / "manifest.json").read_text(encoding="utf8"))
            sha = man["results"]["ct6"]["result"]["sha256"]
        except (OSError, KeyError, TypeError, ValueError):
            continue
        return sha
    return None


def outcome(folder, facts_key):
    """(ok, text, SHA-256 of the result or None) for a finished run, from the session's manifest."""
    try:
        man = json.loads((Path(folder) / "manifest.json").read_text(encoding="utf8"))
        ct6 = man["results"]["ct6"]
    except (OSError, KeyError, TypeError, ValueError) as e:
        return False, "the session's record could not be read (%s)" % e, None
    res = ct6.get("result") or {}
    f = res.get(facts_key) or {}
    sha = res.get("sha256")
    if man.get("status") != "completed":
        return False, "the run did not complete (%s)" % (man.get("error") or man.get("status")), sha
    if not ct6.get("result_found") or not res.get("complete"):
        return False, "the camera gave no complete result", sha
    if f.get("undo_incomplete"):
        return False, "A STEP FAILED AND ITS UNDO DID NOT COMPLETE", sha
    if f.get("done"):
        return True, "done", sha
    if f.get("nothing_to_do"):
        return True, "already in place, nothing to do", sha
    why = "; ".join((f.get("refused") or []) + (f.get("problems") or [])) or "see the lines above"
    return False, ("a step failed and was put back: " if f.get("undone") else "not done: ") + why, sha


def run_step(n, total, level, design, sha, facts_key, what, firmware, clear):
    say()
    say("=" * 78)
    say("Step %d of %d: level %d, %s: %s" % (n, total, level, design, what))
    say("=" * 78)
    cmd = [sys.executable, "-I", "-B", str(RUNNER), "--go", "--level", str(level), "--design", design, "--firmware-shown", firmware, "--library-sha256", sha]
    if clear:
        cmd += ["--clear-result", clear]
    folder = None
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf8", errors="replace", cwd=str(MAP))
    for line in p.stdout:
        line = line.rstrip("\n")
        say("  " + line)
        m = re.match(r"Session folder: (.+)$", line)
        if m:
            folder = m.group(1).strip()
    p.wait()
    if folder is None:
        return False, "the run ended before a session was saved (exit code %d)" % p.returncode, None
    ok, text, got = outcome(folder, facts_key)
    if p.returncode != 0 and ok:
        ok, text = False, "the run ended with exit code %d" % p.returncode
    return ok, text, got


def offline(mode, steps):
    """--dry-run or --selftest of each step, on the runner's simulated camera. Nothing is sent to any device."""
    check_libraries(steps)
    say("The %d pinned libraries are present and have the pinned hashes." % len(steps))
    for n, (level, design, sha, _, what) in enumerate(steps, 1):
        say()
        say("--- step %d: level %d, %s (%s): %s" % (n, level, design, what, mode))
        r = subprocess.run([sys.executable, "-I", "-B", str(RUNNER), mode, "--level", str(level), "--design", design], capture_output=True, text=True,
                           encoding="utf8", errors="replace", cwd=str(MAP))
        lines = r.stdout.strip().splitlines()
        for line in lines[-6:] if mode == "--selftest" else lines[:3] + ["  ..."] + lines[-2:]:
            say("  " + line[:200])
        if r.returncode != 0:
            raise SystemExit("STOP: step %d's %s failed:\n%s" % (n, mode, r.stderr[-800:]))
    say()
    say("All %d steps passed their %s. Nothing was sent to any device." % (len(steps), mode.lstrip("-")))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.set_defaults(hs_only=False, with_xavc_s=False, test=None, lcd32=False, cycle=False)
    ap.add_argument("--real57", action="store_true", help="the real 5760x3840 state (F906): first scaler 5760x3840 (og57n_v1), XAVC HS 4K at 24p, with the rear-screen steps")
    ap.add_argument("--old-lcd", action="store_true", help="use the rear-screen steps as they were before 2026-11-21 (lcdfill_v1, lcdcycle_v5: proven, but no focus frames on the rear screen, F966)")
    ap.add_argument("--rate100", action="store_true", help="5.7K: the encoder step as it was before 2026-11-21 (ogfile57_v1): the menu's own bit rate, at most 100 Mbps, instead of 300 Mbps on the 100M settings")
    ap.add_argument("--no-cycle", action="store_true", help="leave out the C3 anamorphic preview cycle (step 6): C3 keeps its own function in movie mode")
    ap.add_argument("--no-lcd32", action="store_true", help="leave out the rear-screen step: live view squeezed in a 16:9 letterbox, as before 2026-11-19")
    ap.add_argument("--ntsc", action="store_true", help="the camera's NTSC/PAL Selector is on NTSC (24p); without --ntsc or --pal the script asks")
    ap.add_argument("--pal", action="store_true", help="the camera's NTSC/PAL Selector is on PAL (25p, XAVC S 4K): step 2 is the design for drive mode 0x880 (F965)")
    ap.add_argument("--dry-run", action="store_true", help="show what each step would send, on a simulated camera; nothing is sent")
    ap.add_argument("--selftest", action="store_true", help="run each step's self-test on a simulated camera; nothing is sent")
    args = ap.parse_args()
    if sum(bool(x) for x in (args.test, args.hs_only, args.real57)) > 1:
        raise SystemExit("--test, --hs-only and --real57 do not go together. Nothing was sent.")
    st = STATES[args.test or ("real57" if args.real57 else "hs-only" if args.hs_only else "default")]
    steps, formats, size = st["steps"], st["formats"], st["size"]
    if args.lcd32 and LCD_32 not in steps:
        steps = steps + [LCD_32]
    if args.cycle and args.no_lcd32:
        raise SystemExit("--cycle needs the rear-screen step (lcdfill_v2): do not combine it with --no-lcd32. Nothing was sent.")
    if args.no_lcd32:
        steps = [x for x in steps if x not in (LCD_32, CYCLE)]           # the cycle starts from lcdfill's 3:2 state
    if args.no_cycle:
        steps = [x for x in steps if x != CYCLE]
    if args.cycle and CYCLE not in steps:
        if LCD_32 not in steps:
            steps = steps + [LCD_32]
        steps = steps + [CYCLE]
    if args.rate100:
        steps = [ENC_57 if x == ENC_57_300 else x for x in steps]
    if args.old_lcd:
        steps = [{LCD_32: LCD_32_V1, CYCLE: CYCLE_V5}.get(x, x) for x in steps]
    if args.ntsc and args.pal:
        raise SystemExit("--ntsc and --pal do not go together. Nothing was sent.")
    if args.dry_run or args.selftest:
        return offline("--dry-run" if args.dry_run else "--selftest", for_family(steps, "PAL" if args.pal else "NTSC"))

    say(st["title"])
    say("-" * 78)
    family = "PAL" if args.pal else "NTSC" if args.ntsc else ask_family()
    steps, rate = for_family(steps, family), RATE[family]
    if family == "PAL":
        formats = "XAVC S 4K"                     # on PAL the camera's own menu offers XAVC HS 4K at 50p only (Super 35); 25p exists in XAVC S 4K
    say()
    if st["test"]:
        say(st["test"] + ".")
        say()
    say("This writes TEMPORARY settings into the camera's memory, in %d steps. Nothing is" % len(steps))
    say("written to flash. A cold boot (battery out for 10 seconds) removes all of it.")
    say()
    say("Before you start:")
    say("  1. The camera is set to %s: in the menu, set File Format to %s and the frame rate to %s." % (family, formats, rate))
    say("  2. Cold boot the camera: power off, battery out for 10 seconds, battery in.")
    say("  3. Turn it on with the mode dial on STILLS (not movie).")
    if CYCLE in steps or CYCLE_V5 in steps:
        say("     For the C3 cycle nothing needs setting: in movie mode the C3 key itself is taken over (whatever it is")
        say("     assigned to); in stills C3 works as before.")
    say("  4. Connect the USB cable. USB Connection Mode: Mass Storage.")
    say()
    say("While it is applied:")
    say("  - Only %s at %s records properly. Do NOT record in another 4K format or" % (formats, rate))
    say("    frame rate, and stay in full-frame 4K: do not switch to HD or to APS-C/Super 35")
    say("    (a mode that is not set up can stop the camera responding; it then needs a cold boot).")
    for k, line in enumerate(st["notes"]):
        say(("  - " if k == 0 or line[:1].isupper() and st["notes"][k - 1].endswith((".", ")")) else "    ") + line)
    say("  - Do not change the NTSC/PAL Selector while it is applied.")
    if family == "PAL":
        say("  - On PAL use XAVC S 4K: the camera offers XAVC HS 4K at 50p only (Super 35), which this state does not cover.")
        say("  - PAL is new (first camera runs 2026-11-21, one camera): step 2 changes drive mode 0x880, the mode PAL uses for 25p.")
        say("    If the picture looks stretched or the camera restarts, say so.")
    say()
    check_libraries(steps)
    shown = input("Type the firmware version the camera shows (Menu > Setup > Version): ").strip()
    if shown != FIRMWARE:
        raise SystemExit("This is only for firmware %s. Nothing was sent." % FIRMWARE)
    if input("Type YES to write these temporary settings to the camera: ").strip() != "YES":
        raise SystemExit("Not confirmed. Nothing was sent.")

    clear = last_result_sha()
    for n, (level, design, sha, facts_key, what) in enumerate(steps, 1):
        try:
            ready = wait_for_drive(first=(n == 1))
        except KeyboardInterrupt:
            ready = False
        if not ready:
            say()
            say("STOPPED before step %d: the camera did not show as a USB drive." % n)
            if n > 1:
                say("Steps 1 to %d are in the camera's memory, the rest are not. Do not record like this." % (n - 1))
                say(COLD_BOOT)
            raise SystemExit(1)
        ok, text, got = run_step(n, len(steps), level, design, sha, facts_key, what, shown, clear)
        clear = got or clear
        if not ok:
            say()
            say("STOPPED at step %d: %s." % (n, text))
            say("The settings are NOT complete. Do not record like this.")
            if n == 1 and "nothing is written" in text:
                say("Step 1 only works straight after a cold boot with the dial on stills, before movie mode has been used.")
            if level == 5 and "holds neither" in text:
                say("Step 2 was run for a camera set to %s and the camera's stored sensor record is not the %s one. Check Menu > Setup >" % (family, family))
                say("Area/Date > NTSC/PAL Selector and give that answer next time. Nothing of step 2 was written.")
                if family == "PAL":
                    say("If the camera is on PAL: the record of drive mode 0x880 has not been read from a camera yet; send the session folder.")
            say(COLD_BOOT + " Then start again from the list at the top.")
            raise SystemExit(1)
        say()
        say("Step %d: %s." % (n, text))

    say()
    say("=" * 78)
    say("ALL %d STEPS ARE IN PLACE." % len(steps))
    say("=" * 78)
    say("Now:")
    say("  1. Unplug the USB cable. Do not power the camera off.")
    if LCD_32 in steps or LCD_32_V1 in steps:
        say("  2. Turn the dial to movie. The rear screen shows the full-height picture at 3:2, filling the screen.")
    if LCD_32 in steps:
        say("     The focus frames are drawn on the rear screen (since 2026-11-21). For a tracking box on a touched subject,")
        say("     set the camera's touch function to Touch Tracking.")
    if CYCLE in steps or CYCLE_V5 in steps:
        say("     Press C3 to step the rear screen 3:2 -> 2:1 -> 2.4:1 -> 3:2 (say what")
        say("     each press shows). Avoid touching the screen or other buttons while the steps run.")
    else:
        say("  2. Turn the dial to movie. The rear screen shows the full-height picture, squeezed.")
    if st["test"]:
        say("  3. Record a few seconds in %s at %s, stop, and play the clip back." % (formats, rate))
        say("     The file should be %s." % size)
    else:
        say("  3. Record in %s at %s. The file is %s." % (formats, rate, size))
    say()
    say("Remember:")
    say("  - Stay in %s at %s, full frame. Other formats and frame rates do not work in this state." % (formats, rate))
    say("  - Power-off, a restart or a cold boot removes the settings; run this again to get them back.")
    if args.test in ("5.7k", "5.7k-300"):
        say("  - IF IT FAILS: leave the camera on if you can, connect USB, and report what you saw before any cold boot.")
    say("  - When you are done, cold boot the camera to return it to stock.")
    say("  - If the camera misbehaves and will not respond: " + COLD_BOOT)


if __name__ == "__main__":
    main()
