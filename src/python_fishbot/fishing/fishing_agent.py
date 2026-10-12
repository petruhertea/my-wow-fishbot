from pathlib import Path
import csv
import time

import cv2 as cv
import numpy as np
import pyautogui

from .lure_detector import (find_by_difference, find_by_template, find_by_new_red, motion_mask,
                           BiteDetector, max_rise)  # keep lure_detector.py next to this file

import ctypes

WINDOW_TITLE = "World of Warcraft"


def wow_is_foreground():
    """True if the game window is the active window. pyautogui sends keys to WHATEVER is focused,
    so without this a cast can open VS Code's Find box instead. Non-Windows: always True."""
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        buf = ctypes.create_unicode_buffer(256)
        user32.GetWindowTextW(hwnd, buf, 256)
        return WINDOW_TITLE.lower() in buf.value.lower()
    except Exception:
        return True


ASSET = Path(__file__).parent / "assets" / "fishing_target2.jpg"


class FishingAgent:
    # Search region (x0, y0, x1, y1) in image pixels, 1920x1080. Keep it on the WATER only:
    # buildings, trees and forges animate and fool the detector. Check result.png in ./debug/
    # (yellow rectangle = search area) and adjust y0 to sit just below the shoreline.
    SEARCH_ROI = (0, 520, 1920, 1080)   # WATER ONLY. Raise y0 so the shoreline/buildings are excluded
    # If current_image is a cropped game window, put its top-left screen position here.
    SCREEN_OFFSET = (0, 0)
    # Saves before/after/diff/result images + bite deltas for every attempt in ./debug/
    DEBUG = True

    def __init__(self, main_agent):
        self.main_agent = main_agent
        self.fishing_target = cv.imread(str(ASSET))
        if self.fishing_target is None:
            raise FileNotFoundError(ASSET)
        self.fishing_thread = None
        self.attempt = 0
        self.dbg_dir = None
        self.exclude = None
        self.last_method = None

    # ---------- frame helpers ----------
    @staticmethod
    def _to_bgr(img):
        """Accept PIL images or numpy arrays (RGB/BGRA) and return a BGR uint8 array."""
        if img is None:
            return None
        if not isinstance(img, np.ndarray):                  # PIL (RGB) -> BGR
            img = np.array(img.convert("RGB"))[:, :, ::-1]
        elif img.ndim == 3 and img.shape[2] == 4:            # BGRA -> BGR
            img = img[:, :, :3]
        return np.ascontiguousarray(img)

    def _grab(self):
        return self._to_bgr(self.main_agent.current_image)

    def _median_frame(self, n, gap):
        """Median of n frames: removes sparkles, splash particles and single-frame shimmer."""
        frames = []
        for _ in range(n):
            f = self._grab()
            if f is not None:
                frames.append(f)
            time.sleep(gap)
        if not frames:
            return None
        return np.median(np.stack(frames), axis=0).astype(np.uint8)

    def _save(self, name, img):
        if self.DEBUG and self.dbg_dir is not None and img is not None:
            cv.imwrite(str(self.dbg_dir / name), img)

    # ---------- one-line-per-attempt log ----------
    LOG_FIELDS = ["time", "attempt", "method", "center", "outcome", "jump_thr",
                  "rest_median", "rest_spread", "peak_delta", "max_jump", "t_bite", "changed_px"]

    def _log_attempt(self, **kw):
        """Append one row to debug/attempts.csv so a whole session fits in ONE small file."""
        if not self.DEBUG:
            return
        path = Path("debug") / "attempts.csv"
        path.parent.mkdir(exist_ok=True)
        new = not path.exists()
        row = {"time": time.strftime("%H:%M:%S"), "attempt": self.attempt, **kw}
        with open(path, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=self.LOG_FIELDS, restval="")
            if new:
                w.writeheader()
            w.writerow(row)

    # ---------- input safety ----------
    def _wait_for_game(self):
        warned = False
        while not wow_is_foreground():
            if not warned:
                print("WoW isn't the active window - click on the game (waiting)...")
                warned = True
            time.sleep(0.5)

    def _press(self, *keys):
        """Only send keys while the game has focus."""
        self._wait_for_game()
        pyautogui.hotkey(*keys)

    # ---------- casting ----------
    def cast_lure(self):
        self._wait_for_game()                     # frames taken before this point could show another window
        self.attempt += 1
        if self.DEBUG:
            self.dbg_dir = Path("debug") / f"attempt_{self.attempt:03d}"
            self.dbg_dir.mkdir(parents=True, exist_ok=True)
        print(f"Casting... (attempt {self.attempt})")

        pre = []                                  # scene WITHOUT the bobber, spaced out to see what moves
        for _ in range(3):
            f = self._grab()
            if f is not None:
                pre.append(f)
            time.sleep(0.3)
        before = np.median(np.stack(pre), axis=0).astype(np.uint8) if pre else None
        self.exclude = motion_mask(pre) if len(pre) >= 2 else None
        self._press('ctrl', 'f')
        time.sleep(2.5)                           # cast animation + splash
        after = self._median_frame(5, 0.2)        # ~1s of settled frames, median-filtered
        self.find_lure(before, after)

    # ---------- detection ----------
    def find_lure(self, before, after):
        if after is None:
            return
        self._save("before.png", before)
        self._save("after.png", after)

        hit = find_by_template(after, self.fishing_target, roi=self.SEARCH_ROI, threshold=0.85)
        if hit:
            print("Lure found by template", hit); self.last_method = "template"

        if hit is None and before is not None and before.shape == after.shape:
            gd = cv.absdiff(cv.cvtColor(before, cv.COLOR_BGR2GRAY), cv.cvtColor(after, cv.COLOR_BGR2GRAY))
            changed = int((gd > 25).sum())          # a small bobber changes few pixels, so count them
            print(f"Changed pixels: {changed}")
            if changed < 30:
                print("Frames identical - nothing appeared (static image / game not updating?)")
            else:
                hit = find_by_new_red(before, after, roi=self.SEARCH_ROI, exclude=self.exclude)
                if hit:
                    print("Lure found by new red feather", hit); self.last_method = "new_red"
                else:
                    hit = find_by_difference(before, after, roi=self.SEARCH_ROI, exclude=self.exclude)
                    if hit:
                        print("Lure found by frame difference", hit); self.last_method = "diff"
            d = cv.absdiff(cv.cvtColor(before, cv.COLOR_BGR2GRAY), cv.cvtColor(after, cv.COLOR_BGR2GRAY))
            if self.exclude is not None:
                self._save("motion_excluded.png", self.exclude)
            self._save("diff.png", cv.normalize(d, None, 0, 255, cv.NORM_MINMAX))

        if hit:
            dbg = after.copy()
            cv.circle(dbg, hit[:2], 30, (0, 255, 0), 2)
            x0, y0, x1, y1 = self.SEARCH_ROI
            cv.rectangle(dbg, (x0, y0), (x1, y1), (255, 255, 0), 1)
            self._save("result.png", dbg)

        if hit is None:
            print("Lure not found - recasting")
            self._log_attempt(method="none", outcome="NOT_FOUND")
            return
        self.move_to_lure(hit[:2])

    def move_to_lure(self, center):
        ox, oy = self.SCREEN_OFFSET
        pyautogui.moveTo(center[0] + ox, center[1] + oy, duration=1, tween=pyautogui.easeOutQuad)
        self.watch_lure(center)

    # ---------- bite detection ----------
    def _patch(self, center, r=15):
        img = self._grab()
        x, y = center
        p = img[max(y - r, 0):y + r, max(x - r, 0):x + r]
        return cv.cvtColor(p, cv.COLOR_BGR2GRAY).astype(np.float32)

    def watch_lure(self, center, timeout=20):
        """Bite = a SUDDEN JUMP in how much the patch around the bobber differs from its resting look.

        The bobber bobs slowly, so its patch wanders between ~5 and ~12 over several seconds; any
        fixed level threshold eventually gets crossed by a wave crest and pulls the line early
        (about half of the earlier 'bites' were exactly that). A real bite is a step: 17-34 points
        within ~0.35 s on real traces, versus ~5 for bobbing. See BiteDetector in lure_detector.py.
        The jump threshold adapts to this bobber's own wobble, learned over the first second."""
        self._wait_for_game()
        patches, times = [], []
        t0 = time.time()
        while time.time() - t0 < 1.0:
            patches.append(self._patch(center))
            times.append(time.time() - t0)
            time.sleep(0.02)
        ok = [i for i, p in enumerate(patches) if p.shape == patches[0].shape]
        patches = [patches[i] for i in ok]
        times = [times[i] for i in ok]
        base = np.median(np.stack(patches), axis=0)            # median: robust to one odd frame
        rest = [float(np.abs(p - base).mean()) for p in patches]
        med = float(np.median(rest))
        spread = float(np.median(np.abs(np.array(rest) - med))) * 1.4826
        noise_rise = max_rise(list(zip(times, rest)))
        det = BiteDetector(noise_rise=noise_rise)
        print(f"Bite jump threshold: {det.jump_thr:.1f} (resting wobble median {med:.1f}, "
              f"largest resting rise {noise_rise:.1f})")
        if med > 20:
            print("  warning: the patch is very unstable at rest - check result.png (is it on the bobber?)")

        log = []
        start = time.time()
        bite, t_bite = False, ""
        while time.time() - start < timeout:
            cur = self._patch(center)
            if cur.shape == base.shape:
                now = time.time() - start
                delta = float(np.abs(cur - base).mean())
                log.append((round(now, 3), round(delta, 2)))
                if det.update(now, delta):
                    print(f"Bite detected! delta={delta:.1f} (jump {det.pending[2]:.1f}) at t={now:.1f}s")
                    bite, t_bite = True, round(now, 2)
                    self.pull_line()
                    break
            time.sleep(0.02)
        peak = max((d for _, d in log), default=0.0)
        if not bite:
            print(f"No bite - recasting (largest jump {det.last_jump:.1f} vs needed {det.jump_thr:.1f})")
        if self.DEBUG and self.dbg_dir is not None:
            with open(self.dbg_dir / "deltas.csv", "w", newline="") as f:
                w = csv.writer(f); w.writerow(["t", "delta"]); w.writerows(log)
            self._log_attempt(method=self.last_method, center=center,
                              outcome="BITE" if bite else "NO_BITE", jump_thr=round(det.jump_thr, 1),
                              rest_median=round(med, 1), rest_spread=round(spread, 1),
                              peak_delta=round(peak, 1), max_jump=round(det.last_jump, 1), t_bite=t_bite)
            with open(self.dbg_dir / "summary.txt", "w") as f:
                f.write(f"method={self.last_method}\ncenter={center}\nthreshold={det.jump_thr:.2f}\n"
                        f"rest_median={med:.2f}\nrest_spread={spread:.2f}\npeak_delta={peak:.2f}\n"
                        f"max_jump={det.last_jump:.2f}\nt_bite={t_bite}\nbite={bite}\n")

    def pull_line(self):
        print("Pulling line")
        self._press('ctrl', 'f')
        time.sleep(0.010)

    def run(self):
        print("Switch to the WoW window now - starting in 5 seconds...")
        time.sleep(5)
        while True:
            self.cast_lure()
            time.sleep(5)