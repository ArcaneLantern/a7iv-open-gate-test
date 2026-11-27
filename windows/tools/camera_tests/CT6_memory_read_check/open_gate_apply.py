"""Apply an open-gate state to a Sony A7 IV (firmware 6.02) for this power-on: 4K (3840x2560) or, with --real57,
5.7K (5760x3840), each with the rear screen at 3:2 and the C3 de-squeeze preview cycle (3:2 -> 2:1 -> 2.25:1 -> 2.4:1).
The MP4 headers say the file's real size, so editors open it at 3:2 without a remux (Sony's XML still says
3840x2160 16:9). 5.7K is coded without B pictures (no duplicate frames); the camera does not play 5.7K files back.

Temporary: memory only. A cold boot (battery out for 10 seconds) returns the camera to stock.
Run it through open_gate_4k.cmd or open_gate_5.7k.cmd, or on macOS through macos/open_gate_4k.command or
macos/open_gate_5.7k.command.
It asks whether the camera is set to NTSC (24p) or PAL (25p, XAVC S 4K only); step 2 differs between the two.
It also asks whether to switch the camera's movie noise reduction off (temporal and spatial: two more steps).

    --ntsc / --pal   answer that question on the command line
    --nr-off / --nr-on   noise reduction off, or kept, without the question
    --no-cycle   leave out the C3 cycle        --no-lcd32   leave out the rear screen 3:2 and the C3 cycle
    --old-lcd    the rear-screen steps as before 2026-11-21 (no focus frames on the rear screen)
    --rate100    5.7K: the menu's own bit rate (at most 100 Mbps) instead of 300 Mbps on the 100M record settings
                 (the encoder step of 2026-11-20: B pictures, headers 3840x2160)
    --no-meta    the encoder step without the header size (headers 3840x2160, as before 2026-11-24)
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
# 2026-11-24 (the owner: "port the in between 1.5x/2.25:1 ratio for C3"): v6 with a fourth state 2.25:1 for 1.5x anamorphic lenses between 2:1
# and 2.4:1 (build/build_lcdcycle_v7.py, F988). Same cave and hook as v6, so it needs a cold boot first if v6 is in place. Used by the meta tests.
CYCLE_V7 = (19, "lcdcycle_v7", "306b255606bd39454785e40e9244ab004db6646d362f524eb6c45008fbe748ae", "level1920",
            "the C3 key steps the rear-screen preview 3:2 -> 2:1 -> 2.25:1 -> 2.4:1 in movie mode and keeps the focus frames (appFw code; v7 = v6, "
            "which works on the camera, F969, plus the 2.25:1 state for 1.5x lenses)")
CYCLES = (CYCLE, CYCLE_V5, CYCLE_V7)
ENC_57 = (19, "ogfile57_v1", "aa1f318fafe1a71a5286b076c2f4fc274f68f196aeaf9bf8518b4841dd2c5f8a", "level1920",
          "the encoder side for 5760x3840: both cores, memory, XAVC HS 4K and XAVC S 4K")
# 2026-11-21, a test the owner asked for: ENC_57 with the 100M record settings at 300 Mbps (build/build_og57.py --rate300; the rate figures and
# the level of Sony's own dormant 5760x3240 profiles). Works on the camera and the blocking seen at 100 Mbps is gone (F971): step 4 of the
# 5.7K state since 2026-11-21. ENC_57 is what --rate100 puts back.
ENC_57_300 = (19, "ogfile57r300_v1", "56f4af121f1b944fb50e94924035af3212b4e041ee3393e39d20d90a08693c75", "level1920",
              "the encoder side for 5760x3840 with the 100M record settings at 300 Mbps: both cores, memory, XAVC HS 4K and XAVC S 4K")
# 2026-11-24, after F981 (the owner: "Fix the frame offset, then Extend M=1 to XAVC S"): M = 1 in all 29 descriptors and the recorder's edit
# list starting at 0 (build/build_og57.py --rate300 --m1all). Since 2026-11-24 (F986) v3: v2's site 0x118004 did not reach a normal recording's
# edit list (C0556 still started one frame in); v3 changes 0x11f4e0 in 0x11f030 instead, for HEVC only (AVC's one frame is right, C0557).
ENC_57_300_M1ALL = (19, "ogfile57r300m1_v3", "65e77094e90af45556ed9ae3c743b538f716ffc325a7b2629b41bdc5f606b36c", "level1920",
                    "the encoder side for 5760x3840 at 300 Mbps on the 100M settings, every record setting of XAVC HS 4K and XAVC S 4K "
                    "with I and P pictures only (M = 1), and an HEVC recording's MP4 edit list starting at 0 (one libmpr.so instruction)")
# 2026-11-24 (the owner: "add the correct metadata tags inside the sony stream so we dont have to remux with ffmpeg"; F987, modding/MP4_META.md):
# the MP4 headers (tkhd, the stsd entry, Sony's PROF box) state the stream's own size. Sony's XML stays 3840x2160 16:9.
ENC_HS_S_V2 = (19, "ogfile2560_hs_s_v2", "cbd83147596c92ba5c5f715fc336d09839576a94673af2644b4021fa2f60964d", "level1920",
               "the encoder side for XAVC HS 4K and XAVC S 4K, and the MP4 headers saying 3840x2560 (v1 plus two libmpr.so heights)")
ENC_57_300_M1_V4 = (19, "ogfile57r300m1_v4", "cbd9c4e942676ca29f62acd966ba73750919d416c0641dbe7447c471480296ad", "level1920",
                    "the encoder side for 5760x3840 at 300 Mbps on the 100M settings, I and P pictures only in every record setting, an HEVC "
                    "recording's edit list starting at 0, and the MP4 headers saying 5760x3840 (v3 plus nine libmpr.so sites)")
# 2026-11-25 (the owner, after ENC_SI_57 worked at 24p, F1014: "build a variant of the 5.7K S-I script, and attempt to make it use HEVC in S-I mode
# (so I frames only)"; build/build_ogfile_sih.py): the same place in the 5.7K state, INSTEAD of ENC_SI_57. XAVC S-I 4K is asked as HEVC, coded as
# I pictures only, in an hvc1 MP4. ENC_SIH_57 is an HEVC intra channel (PredMode 0, as HEIF stills; S-I's 240M/250M per-picture budget);
# ENC_SIH_57_P1 (--hevc-gop1) is the fallback: the I/P channel XAVC HS uses at 5.7K, with a GOP of one picture. Not run when written.
ENC_SIH_57 = (19, "ogfilesih57_v1", "d7427d2c895a52fa2b16e7d48aecb8fa3f0de67b192f8274e0b175a11387be98", "level1920",
              "XAVC S-I 4K recorded as HEVC 4:2:2 10-bit, I pictures only, at 5760x3840: an HEVC intra channel (PredMode 0, M 0, N 1, S-I's own "
              "bits per picture) in an hvc1 MP4")
ENC_SIH_57_P1 = (19, "ogfilesih57p1_v1", "0c605aea3853809c23c0c8da53756d4c31711b77262d96db376a210392f6d095", "level1920",
                 "XAVC S-I 4K recorded as HEVC 4:2:2 10-bit, I pictures only, at 5760x3840: the I/P channel of XAVC HS with a GOP of one picture "
                 "(PredMode 1, M 1, N 1, Sony's 300 Mbps figures) in an hvc1 MP4")
# 2026-11-25, after ENC_SIH_57_P1 worked (F1017) with a 10-picture rate-control cycle (every 10th picture ~3x the bits, ~13 QP finer): two
# bisection variants on the same channel, about 300 Mb/s as bits per picture. --hevc-gop1-intrarc: the intra rate-control set-up of AVC S-I and
# HEIF (M 0, rates 0, per-picture budget); --hevc-gop1-bits: ENC_SIH_57_P1 plus the per-picture budget. Not run when written.
ENC_SIH_57_P2 = (19, "ogfilesih57p2_v1", "5c62681a84ed6884e36a5acc9b175de91b1782c9a64246674bcd6af1cd46ef7f", "level1920",
                 "XAVC S-I 4K as HEVC, I pictures only, 5760x3840: the I/P channel with the intra rate-control set-up (M 0, N 1, rate fields 0, "
                 "about 300 Mb/s as bits per picture)")
ENC_SIH_57_P3 = (19, "ogfilesih57p3_v1", "4266fef9a657418aee507751f307d0daf3878a3dce9b41b044455efe1ff98ab8", "level1920",
                 "XAVC S-I 4K as HEVC, I pictures only, 5760x3840: the --hevc-gop1 step plus a per-picture budget of about 300 Mb/s")
# 2026-11-21: step 2 for a camera set to PAL: the same design moved to drive mode 0x880, which PAL uses for full-frame 4K 25p, with the
# stored record of that mode in the PAL family's bytes (build/build_mode880.py). Keyed by the NTSC design's name. A state whose step 2
# is not here has no PAL build. Both applied and worked on the camera on 2026-11-21 (F965).
PAL_SQ = (5, "ogsq880_v1", "f7db0d936713a2a41acdfc7746828ea7d0a201b32fc58a166529bbf519620636", "level56",
          "the full-height picture, every sensor row, in drive mode 0x880 (camera set to PAL, 25p)")
PAL_57N = (5, "og57n880_v1", "e2908a73cecab247d5d37be5d757beeb9a1c30fcf60f55aa0a481b93af527760", "level56",
           "the full-height picture, 5760x3840 out of the first scaler, in drive mode 0x880 (camera set to PAL, 25p)")
PAL = {"ogsq_v3": PAL_SQ, "og57n_v1": PAL_57N}
# 2026-11-26 (the owner: "open gate in S35 mode for 50p and 60p ... a 3840x2560 option and a ~4672x3114 ... option"; build/build_og_s35.py,
# modding/OGS35_TEST.md): Super 35 4K at 59.94p (NTSC) and 50p (PAL) runs drive mode 0x821. Step 1 is the sensor side: the sensor's own window
# 4672x3120 from row 774 in a new register-matrix column (0x821 only), the mode's tables and picture records, and its stored record. The library
# carries the NTSC and the PAL record (MULTI_REC) and writes the one the camera holds, so the same step serves both. No raw-buffer step: the
# 3,136-row stage fits the stock raw write buffer (3,958 rows). The encoder steps set up 59.94p and 50p only. None of this has run on a camera.
PIC_S35SQ = (5, "og35sq_v1", "d9ad9728f4b388acc53c7fb2af568a4602b90fbba68a1fc0d0dc5832f963863a", "level56",
             "the Super 35 window made 3:2 (4672x3120 from sensor row 774, drive mode 0x821, a new sensor-register column), squeezed into the stock "
             "4336x2438 first-scaler picture")
PIC_S35N = (5, "og35n_v1", "d79527c8f4f028cf2324414b71d9afcba1e86d77eb318c636d4e230c55172c86", "level56",
            "the Super 35 window made 3:2 (4672x3120 from sensor row 774, drive mode 0x821, a new sensor-register column), 4672x3120 out of the "
            "first scaler, one to one")
UNITS2 = (16, "units2_v1", "8b773f08b551f8b8d95422a524ecf11802d614ab2ae771618bfe68100b87e152", "level1617",
          "the unit-count setting to 0: two scaler units for 4K (the owner's camera comes up with four since 2026-11-19, F800)")
# Test 0 of request 77 (the owner: "Build band test"; build/build_og_s35_band.py): the same sensor side, but the first crop takes the STOCK band
# back out of the taller window, so everything after it is stock. One step, on a stock camera: the picture must look exactly like stock S35 4K.
PIC_S35BAND = (5, "og35band_v1", "55401f055f384769e1459722e147267b669a769e86eb1de490f045b8b31c363f", "level56",
               "the Super 35 sensor window made 3:2 (4672x3120 from sensor row 774, drive mode 0x821, a new sensor-register column), the first crop "
               "taking the stock 4672x2628 band back out of it: everything after it stock")
PAL.update({"og35sq_v1": PIC_S35SQ, "og35n_v1": PIC_S35N, "og35band_v1": PIC_S35BAND})     # one library for NTSC and PAL (the stored record's two variants)
S35_TESTS = ("s35-2560", "s35-native", "s35-band")
# 2026-11-27, request 78 (the owner: "temporal noise reduction can be disabled and spatial can be turned down or even to 0, make a plan to
# implement this in a test script with the open gate modules we have so far (4k, 5.7k 300mbps)"). build/build_nr_words.py, modding/NR_TEST.md.
# NRV_OFF is the firmware's own override for the temporal stage; NRS_GATE is an experiment on the spatial stage (--spatial). Both go last, so a
# refusal leaves the open gate state before them complete. Not run on a camera.
NRV_OFF = (16, "nrvoff_v1", "767a7baffb48446f6cf6e950a3e4376719207fd57f4606d69ab76246869e3385", "level1617",
           "temporal noise reduction off in movie: the firmware's own override byte for the temporal stage's functions, 0 to 1")
# 2026-11-27 (the owner: "trace and find out where spatial noise reduction happens and how to control it"; F1053): the spatial stage's own
# developer switch. Replaces NRS_GATE behind --spatial; NRS_GATE stays pinned but no flag uses it. Not run on a camera.
NRS_OFF = (16, "nrsoff_v1", "5ff2dc8e4988f00c9bf52b0d89416535705616c4506d6201a25ff9c4a608e199", "level1617",
           "spatial noise reduction off: the firmware's own developer switch CamNrOnOff (byte 0x1a39189), 0 to 1")
NR_TESTS = ("nr-4k", "nr-5.7k")
RATE = {"NTSC": "24p", "PAL": "25p"}
BOTH = "XAVC HS 4K or XAVC S 4K"
STATES = {
    "default": {"steps": BASE + [OUT_2560, ENC_HS_S_V2, LCD_32, CYCLE_V7], "formats": BOTH, "size": "3840x2560", "test": None,
                "title": "Open gate for the Sony A7 IV: a 3840x2560 recording of the whole 3:2 sensor area",
                "notes": ["The rear screen shows the whole picture at 3:2 while shooting (step 5); every 16:9 picture on the rear screen fills it too. The file is",
                          "3840x2560 and plays back in the camera at 3:2. Its MP4 headers say 3840x2560, so editors such as DaVinci Resolve",
                          "show it at 3:2 without a remux; Sony's own XML in the file still says 3840x2160 16:9. Set Proxy Recording to Off.",
                          "C3 steps the rear screen 3:2 -> 2:1 (1.33x) -> 2.25:1 (1.5x) -> 2.4:1 (1.6x) in movie mode."]},
    "real57": {"steps": BASE[:1] + [PIC_57N, OUT_57, ENC_57_300_M1_V4, LCD_32, CYCLE_V7], "formats": BOTH, "size": "5760x3840", "test": None,
               "title": "Open gate for the Sony A7 IV: a real 5760x3840 recording of the whole 3:2 sensor area",
               "notes": ["The file is 5760x3840 with real detail: the first scaler gives 5760x3840 and nothing is enlarged (F906). Its MP4",
                         "headers say 5760x3840, so editors such as DaVinci Resolve show it at 3:2 without a remux; Sony's own XML in the file",
                         "still says 3840x2160 16:9. The camera does not play these files back. Set Proxy Recording to Off.",
                         "Every record setting is coded with I and P pictures only (no B pictures): that removed the duplicate frames.",
                         "The record settings marked 100M record at about 300 Mbps (peaks to 340): at 100 Mbps this size showed blocking (F971).",
                         "The lower record settings keep their own bit rate. The menu and the remaining time still say 100M: the card fills",
                         "three times as fast as shown. Use a fast card (about 40 MB a second: CFexpress Type A, or SD V60 / V90).",
                         "C3 steps the rear screen 3:2 -> 2:1 (1.33x) -> 2.25:1 (1.5x) -> 2.4:1 (1.6x) in movie mode.",
                         "--rate100 gives the step 4 of 2026-11-20, with the menu's own bit rate (and B pictures).",
                         "Not yet tried in this state: long recordings (heat).",
                         "IF THE CAMERA RESTARTS OR FREEZES: do not cold boot; connect USB and say so (level 10 reads the crash report)."]},
}


NR_SPATIAL_NOTES = ["Spatial step: the firmware's own developer switch for the spatial noise-reduction stage (CamNrOnOff) is set",
                    "to off. Expect finer, sharper-looking grain and more chroma noise. It has not run on a camera: it may do",
                    "nothing (if the camera resets the switch) or spoil the picture. It also reaches photographs taken meanwhile.",
                    "Compare with a clip made without --spatial, so the two effects can be told apart."]
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


NR_OFF_NOTES = ["Noise reduction OFF: the camera's own switches for movie noise reduction are set (temporal and spatial). Expect",
                "more and finer grain, most visible from ISO 12800 (about 1.45x the noise in the shadows there), and no smoothing of",
                "fine detail. The switches also reach photographs taken while it is applied. A cold boot turns noise reduction back on."]


def ask_nr():
    say()
    say("Noise reduction: the camera's movie noise reduction can be switched off (temporal and spatial; more, finer grain).")
    answer = input("Type OFF to switch it off, or press Enter to keep it: ").strip().upper()
    if answer in ("OFF", "Y", "YES"):
        return True
    if answer in ("", "N", "NO", "ON", "KEEP"):
        return False
    raise SystemExit("Neither OFF nor Enter. Nothing was sent.")


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
    ap.set_defaults(hs_only=False, with_xavc_s=False, test=None, lcd32=False, cycle=False, spatial=False, spatial_only=False)
    ap.add_argument("--real57", action="store_true", help="the real 5760x3840 state (F906): first scaler 5760x3840 (og57n_v1), XAVC HS 4K at 24p, with the rear-screen steps")
    ap.add_argument("--hevc-gop1", action="store_true", help="with --test si-hevc-5.7k: the fallback step ogfilesih57p1_v1 (XAVC HS's I/P channel with a GOP of one picture) "
                                                             "instead of the HEVC intra channel")
    ap.add_argument("--hevc-gop1-intrarc", action="store_true", help="with --test si-hevc-5.7k: ogfilesih57p2_v1, the --hevc-gop1 channel with the intra "
                                                                     "rate-control set-up (M 0, rates 0, a per-picture budget of about 300 Mb/s); a test of the 10-frame pulse")
    ap.add_argument("--hevc-gop1-bits", action="store_true", help="with --test si-hevc-5.7k: ogfilesih57p3_v1, the --hevc-gop1 step plus a per-picture budget "
                                                                  "of about 300 Mb/s; a test of the 10-frame pulse")
    ap.add_argument("--old-lcd", action="store_true", help="use the rear-screen steps as they were before 2026-11-21 (lcdfill_v1, lcdcycle_v5: proven, but no focus frames on the rear screen, F966)")
    ap.add_argument("--rate100", action="store_true", help="5.7K: the encoder step as it was before 2026-11-21 (ogfile57_v1): the menu's own bit rate, at most 100 Mbps, instead of 300 Mbps on the 100M settings (B pictures and the MP4 header size as then)")
    ap.add_argument("--no-meta", action="store_true", help="the encoder step without the MP4 header size (before 2026-11-24): the headers say 3840x2160 as the camera's own (4K: ogfile2560_hs_s_v1; 5.7K: ogfile57r300m1_v3)")
    ap.add_argument("--two-units", action="store_true", help="with --test s35-2560 or s35-band: one more step, units2_v1, so that 4K runs on two scaler "
                                                             "units (the owner's camera comes up with four since 2026-11-19, F800); a test of the slow 60p timer")
    ap.add_argument("--no-cycle", action="store_true", help="leave out the C3 anamorphic preview cycle (step 6): C3 keeps its own function in movie mode")
    ap.add_argument("--no-lcd32", action="store_true", help="leave out the rear-screen step: live view squeezed in a 16:9 letterbox, as before 2026-11-19")
    ap.add_argument("--nr-off", action="store_true", help="switch the camera's movie noise reduction off (temporal and spatial): two more steps at "
                                                          "the end, nrvoff_v1 and nrsoff_v1 (proven on the camera, F1058); without --nr-off or --nr-on the script asks")
    ap.add_argument("--nr-on", action="store_true", help="keep the camera's noise reduction (no question)")
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
        steps = [x for x in steps if x != LCD_32 and x not in CYCLES]   # the cycle starts from lcdfill's 3:2 state
    if args.no_cycle:
        steps = [x for x in steps if x not in CYCLES]
    if args.cycle and not any(x in steps for x in CYCLES):
        if LCD_32 not in steps:
            steps = steps + [LCD_32]
        steps = steps + [CYCLE_V7]
    if args.rate100:
        if args.test in ("5.7k-300-m1", "5.7k-300-m1all", "5.7k-meta"):
            raise SystemExit("--rate100 does not go with the M = 1 tests: they are 300 Mbps tests. Nothing was sent.")
        if args.test == "si-hevc-5.7k":
            raise SystemExit("--rate100 does not go with the HEVC S-I test: its MP4 track takes the 5760x3840 size from step 4's header sites. Nothing was sent.")
        steps = [ENC_57 if x in (ENC_57_300, ENC_57_300_M1_V4) else x for x in steps]
    if args.no_meta:
        if ENC_SIH_57 in steps:
            raise SystemExit("--no-meta does not go with the HEVC S-I test: its MP4 track takes the 5760x3840 size from step 4's header sites. Nothing was sent.")
        steps = [{ENC_HS_S_V2: ENC_HS_S, ENC_57_300_M1_V4: ENC_57_300_M1ALL}.get(x, x) for x in steps]
    chosen = [(flag, step) for flag, step in (("--hevc-gop1", ENC_SIH_57_P1), ("--hevc-gop1-intrarc", ENC_SIH_57_P2), ("--hevc-gop1-bits", ENC_SIH_57_P3))
              if getattr(args, flag[2:].replace("-", "_"))]
    if len(chosen) > 1:
        raise SystemExit("Choose one of --hevc-gop1, --hevc-gop1-intrarc, --hevc-gop1-bits. Nothing was sent.")
    if chosen:
        if ENC_SIH_57 not in steps:
            raise SystemExit("%s goes with --test si-hevc-5.7k only. Nothing was sent." % chosen[0][0])
        steps = [chosen[0][1] if x == ENC_SIH_57 else x for x in steps]
    if args.two_units:
        if args.test not in ("s35-2560", "s35-band"):
            raise SystemExit("--two-units goes with --test s35-2560 or --test s35-band. Nothing was sent.")
        at = steps.index(OUT_2560) + 1 if OUT_2560 in steps else 1
        steps = steps[:at] + [UNITS2] + steps[at:]
    if st.get("ntsc_only") and args.pal:
        raise SystemExit("This test changes only XAVC HS 4K 24p 100M 4:2:2 10bit, which a camera set to PAL does not offer. Set the "
                         "NTSC/PAL Selector to NTSC for it. Nothing was sent.")
    if args.old_lcd:
        steps = [{LCD_32: LCD_32_V1, CYCLE: CYCLE_V5, CYCLE_V7: CYCLE_V5}.get(x, x) for x in steps]
    if args.spatial or args.spatial_only:
        if args.test not in NR_TESTS:
            raise SystemExit("--spatial and --spatial-only go with --test nr-4k or --test nr-5.7k. Nothing was sent.")
        if args.spatial and args.spatial_only:
            raise SystemExit("Choose one of --spatial (both steps) and --spatial-only. Nothing was sent.")
        steps = [x for x in steps if x != NRV_OFF] + ([NRV_OFF] if args.spatial else []) + [NRS_OFF]      # the noise-reduction steps stay last
        head = st["notes"][:5] if args.spatial else ["THIS IS A TEST of the spatial step alone. Temporal noise reduction stays as the camera has it."]
        st = dict(st, notes=head + NR_SPATIAL_NOTES + st["notes"][6:])
    elif args.test in NR_TESTS:
        steps = [x for x in steps if x != NRV_OFF] + [NRV_OFF]                      # last, whatever the rear-screen flags did
    if args.ntsc and args.pal:
        raise SystemExit("--ntsc and --pal do not go together. Nothing was sent.")
    if args.nr_off and args.nr_on:
        raise SystemExit("--nr-off and --nr-on do not go together. Nothing was sent.")
    if (args.nr_off or args.nr_on) and args.test:
        raise SystemExit("--nr-off and --nr-on go with the 4K and 5.7K states, not with --test (the noise tests have their own steps). Nothing was sent.")
    nr_off = True if args.nr_off else False if (args.nr_on or args.test) else None       # None: ask in the live run
    if args.dry_run or args.selftest:
        return offline("--dry-run" if args.dry_run else "--selftest", for_family(steps + ([NRV_OFF, NRS_OFF] if nr_off else []), "PAL" if args.pal else "NTSC"))

    say(st["title"])
    say("-" * 78)
    family = "PAL" if args.pal else "NTSC" if args.ntsc else ask_family()
    if nr_off is None:
        nr_off = ask_nr()
    if nr_off:
        steps = steps + [NRV_OFF, NRS_OFF]                                          # last: a refusal there leaves the open gate state complete
        st = dict(st, notes=st["notes"] + NR_OFF_NOTES)
    if st.get("ntsc_only") and family != "NTSC":
        raise SystemExit("This test changes only XAVC HS 4K 24p 100M 4:2:2 10bit, which a camera set to PAL does not offer. Set the "
                         "NTSC/PAL Selector to NTSC for it. Nothing was sent.")
    steps, rate = for_family(steps, family), st.get("rates", RATE)[family]
    if family == "PAL":
        formats = st.get("pal_formats", "XAVC S 4K")   # on PAL the camera's own menu offers XAVC HS 4K at 50p only (Super 35); 25p exists in XAVC S 4K (and S-I 4K)
    say()
    if st["test"]:
        say(st["test"] + ".")
        say()
    say("This writes TEMPORARY settings into the camera's memory, in %d steps. Nothing is" % len(steps))
    say("written to flash. A cold boot (battery out for 10 seconds) removes all of it.")
    say()
    say("Before you start:")
    say("  1. The camera is set to %s: in the menu, set File Format to %s and the frame rate to %s." % (family, formats, rate))
    if st.get("s35"):
        say("     Record Setting: any 4K %s setting. 4K %s is always Super 35 on this camera (APS-C S35 is used by itself)." % (rate.split()[0], rate.split()[0]))
        say("     Proxy Recording: Off.")
    say("  2. Cold boot the camera: power off, battery out for 10 seconds, battery in.")
    say("  3. Turn it on with the mode dial on STILLS (not movie).")
    if any(x in steps for x in CYCLES):
        say("     For the C3 cycle nothing needs setting: in movie mode the C3 key itself is taken over (whatever it is")
        say("     assigned to); in stills C3 works as before.")
    if CYCLE_V7 in steps:
        say("     The cold boot matters here: this C3 step is refused while the earlier one (open_gate_apply.cmd) is applied.")
    say("  4. Connect the USB cable. USB Connection Mode: Mass Storage.")
    say()
    say("While it is applied:")
    if st.get("band"):
        say("  - Only drive mode 0x821 changes (Super 35 4K at 25p, 30p, 50p and 60p): its picture should be stock. Full frame, Super 35")
        say("    4K 24p and Super 35 HD are not touched. The encoder is not touched.")
    elif st.get("s35"):
        say("  - Only %s at %s (Super 35) records properly. Do NOT record in another 4K format or" % (formats, rate))
        say("    frame rate, and do not record full-frame 4K (24p/25p/30p) in this state: the encoder is set for the new size")
        say("    (a mode that is not set up can stop the camera responding; it then needs a cold boot).")
    else:
        say("  - Only %s at %s records properly. Do NOT record in another 4K format or" % (formats, rate))
        say("    frame rate, and stay in full-frame 4K: do not switch to HD or to APS-C/Super 35")
        say("    (a mode that is not set up can stop the camera responding; it then needs a cold boot).")
    for k, line in enumerate(st["notes"]):
        say(("  - " if k == 0 or line[:1].isupper() and st["notes"][k - 1].endswith((".", ")")) else "    ") + line)
    say("  - Do not change the NTSC/PAL Selector while it is applied.")
    if st.get("s35"):
        say("  - Step 1 carries the stored sensor record for NTSC (59.94p) and for PAL (50p) and writes the one the camera holds.")
    elif family == "PAL" and st.get("pal_formats"):
        say("  - On PAL: XAVC S-I 4K at 25p (and XAVC S 4K at 25p as a control). That S-I 25p uses the same full-frame mode as")
        say("    XAVC S 4K 25p (drive mode 0x880) is assumed, not read from a camera: if the picture looks stretched, say so.")
    elif family == "PAL":
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
    if CYCLE_V7 in steps:
        say("     Press C3 to step the rear screen 3:2 -> 2:1 -> 2.25:1 -> 2.4:1 -> 3:2 (say what")
        say("     each press shows). Avoid touching the screen or other buttons while the steps run.")
    elif CYCLE in steps or CYCLE_V5 in steps:
        say("     Press C3 to step the rear screen 3:2 -> 2:1 -> 2.4:1 -> 3:2 (say what")
        say("     each press shows). Avoid touching the screen or other buttons while the steps run.")
    elif st.get("look"):
        for line in st["look"]:
            say(line)
    else:
        say("  2. Turn the dial to movie. The rear screen shows the full-height picture, squeezed.")
    if st.get("record"):
        for line in st["record"]:
            say(line % rate if "%s" in line else line)
    elif st["test"]:
        say("  3. Record a few seconds in %s at %s, stop, and play the clip back." % (formats, rate))
        say("     The file should be %s." % size)
    else:
        say("  3. Record in %s at %s. The file is %s." % (formats, rate, size))
    say()
    say("Remember:")
    if st.get("band"):
        say("  - This state records the stock 3840x2160 file in every mode; only the sensor window of Super 35 4K 25p-60p is changed.")
    else:
        say("  - Stay in %s at %s, %s. Other formats and frame rates do not work in this state." % (formats, rate, "Super 35" if st.get("s35") else "full frame"))
    say("  - Power-off, a restart or a cold boot removes the settings; run this again to get them back.")
    if args.test in ("5.7k", "5.7k-300", "5.7k-300-m1", "5.7k-300-m1all", "5.7k-300-slot8", "4k-meta", "5.7k-meta", "si-4k", "si-5.7k", "si-hevc-5.7k", "s-hevc-4k", "s-hevc-5.7k") + S35_TESTS + NR_TESTS:
        say("  - IF IT FAILS: leave the camera on if you can, connect USB, and report what you saw before any cold boot.")
    say("  - When you are done, cold boot the camera to return it to stock.")
    say("  - If the camera misbehaves and will not respond: " + COLD_BOOT)


if __name__ == "__main__":
    main()
