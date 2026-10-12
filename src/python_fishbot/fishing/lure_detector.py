"""Bobber detection that doesn't depend on the bobber's colour (which changes per zone / time of day)."""
import cv2 as cv
import numpy as np


def find_by_difference(before, after, roi=None, min_area=60, max_area=6000, exclude=None):
    """Locate the bobber as the blob that appeared between two frames (before cast / after landing).

    Returns (x, y, confidence) in full-image coordinates, or None.
    """
    h, w = after.shape[:2]
    x0, y0, x1, y1 = roi if roi else (0, 0, w, h)
    a = cv.GaussianBlur(cv.cvtColor(before[y0:y1, x0:x1], cv.COLOR_BGR2GRAY), (5, 5), 0)
    b = cv.GaussianBlur(cv.cvtColor(after[y0:y1, x0:x1], cv.COLOR_BGR2GRAY), (5, 5), 0)
    # remove global brightness drift (day/night cycle, fog) before differencing
    b = cv.convertScaleAbs(b.astype(np.float32) - (b.mean() - a.mean()))
    diff = cv.absdiff(a, b)
    # adaptive threshold: well above the noise floor of this particular scene
    thr = max(12, float(np.median(diff)) + 4 * float(diff.std()))
    mask = (diff > thr).astype(np.uint8) * 255
    if exclude is not None:                     # animated scenery seen BEFORE the cast
        mask[exclude[y0:y1, x0:x1] > 0] = 0
    mask = cv.morphologyEx(mask, cv.MORPH_CLOSE, cv.getStructuringElement(cv.MORPH_ELLIPSE, (9, 9)))
    n, _, stats, cents = cv.connectedComponentsWithStats(mask)
    best = None
    for i in range(1, n):
        area = stats[i, cv.CC_STAT_AREA]
        if not (min_area <= area <= max_area):
            continue
        bw, bh = stats[i, cv.CC_STAT_WIDTH], stats[i, cv.CC_STAT_HEIGHT]
        compact = area / float(bw * bh)           # blobs, not thin streaks (rain, line)
        score = area * compact
        if best is None or score > best[0]:
            best = (score, cents[i], compact)
    if best is None:
        return None
    cx, cy = best[1]
    return int(cx + x0), int(cy + y0), float(best[2])


def find_by_template(image, template, roi=None, threshold=0.80):
    """Fallback: plain template match, but only accepted above a confidence threshold.

    Returns the CENTRE of the match as (x, y, score), or None.
    """
    h, w = image.shape[:2]
    x0, y0, x1, y1 = roi if roi else (0, 0, w, h)
    res = cv.matchTemplate(image[y0:y1, x0:x1], template, cv.TM_CCOEFF_NORMED)
    _, score, _, loc = cv.minMaxLoc(res)
    if score < threshold:
        return None
    th, tw = template.shape[:2]
    return int(loc[0] + tw // 2 + x0), int(loc[1] + th // 2 + y0), float(score)


def _red_mask(img):
    """Saturated red/orange pixels (the bobber's feather). Works regardless of zone brightness
    as long as the water itself isn't red."""
    hsv = cv.cvtColor(img, cv.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    return (((h < 12) | (h > 170)) & (s > 110) & (v > 50)).astype(np.uint8)


def find_by_new_red(before, after, roi=None, min_area=12, max_area=900, exclude=None):
    """Find red feather pixels that are present after the cast but weren't there before.
    Combines 'what changed' with 'what colour' so animated scenery (forge bellows, trees,
    reflections) is ignored. Returns (x, y, confidence) or None."""
    h, w = after.shape[:2]
    x0, y0, x1, y1 = roi if roi else (0, 0, w, h)
    ra = _red_mask(after[y0:y1, x0:x1])
    rb = _red_mask(before[y0:y1, x0:x1])
    rb = cv.dilate(rb, np.ones((9, 9), np.uint8))          # tolerate small shifts
    new = (ra & (1 - rb)) * 255
    if exclude is not None:
        new[exclude[y0:y1, x0:x1] > 0] = 0
    new = cv.morphologyEx(new, cv.MORPH_CLOSE, cv.getStructuringElement(cv.MORPH_ELLIPSE, (7, 7)))
    n, _, stats, cents = cv.connectedComponentsWithStats(new)
    cands = []
    for i in range(1, n):
        a = stats[i, cv.CC_STAT_AREA]
        if not (min_area <= a <= max_area):
            continue
        w, h = stats[i, cv.CC_STAT_WIDTH], stats[i, cv.CC_STAT_HEIGHT]
        streak = max(w, h) / float(max(1, min(w, h))) > 6     # thin line-like streak, not a feather
        cands.append((a, cents[i], streak))
    if not cands:
        return None
    # The red fishing line runs from the bobber UP toward the rod, so the bobber's feather is the
    # lowest red blob on screen. Picking the biggest blob instead can latch onto the line (this
    # happened in ~1 of 6 casts: cursor near the horizon, no bite).
    solid = [c for c in cands if not c[2]] or cands
    biggest = max(c[0] for c in solid)
    solid = [c for c in solid if c[0] >= 0.25 * biggest]
    best = max(solid, key=lambda c: c[1][1])                  # largest y = lowest on screen
    best = (best[0], best[1])
    cx, cy = best[1]
    # the red feather sits up-left of the bobber's body; nudge toward the centre of the whole bobber
    return int(cx + x0 + 8), int(cy + y0 + 12), min(1.0, best[0] / 150.0)


def motion_mask(frames, thr=10, grow=25):
    """Pixels that already move between pre-cast frames (forge bellows, leaves, reflections).
    Returns a uint8 mask (255 = ignore)."""
    g = [cv.GaussianBlur(cv.cvtColor(f, cv.COLOR_BGR2GRAY), (5, 5), 0) for f in frames]
    m = np.zeros_like(g[0])
    for i in range(len(g)):
        for j in range(i + 1, len(g)):
            m = np.maximum(m, cv.absdiff(g[i], g[j]))
    m = (m > thr).astype(np.uint8) * 255
    return cv.dilate(m, cv.getStructuringElement(cv.MORPH_ELLIPSE, (grow, grow)))


from collections import deque


def max_rise(samples, window=0.35):
    """Largest rise of the signal within any `window` seconds. samples = [(t, value), ...]."""
    best, hist = 0.0, deque()
    for t, v in samples:
        while hist and t - hist[0][0] > window:
            hist.popleft()
        if hist:
            best = max(best, v - min(x for _, x in hist))
        hist.append((t, v))
    return best


class BiteDetector:
    """Detects a bite as a SUDDEN JUMP in the patch-change signal, not as a high absolute level.

    Why: the bobber bobs slowly (waves of ~5-12 over several seconds), so any fixed level
    threshold eventually gets crossed by a wave crest and pulls the line early. A real bite is a
    step: on real traces it rose 17-34 within 0.35s, while bobbing never rose more than ~5.

      jump  = delta - (lowest delta in the last `window` seconds)
      bite  = jump >= jump_thr  and  delta >= min_level  and it STAYS up for `sustain` seconds
    jump_thr adapts to the bobber's own wobble: mult x (largest rise seen while resting).
    """

    def __init__(self, noise_rise=0.0, min_jump=10.0, max_jump=30.0, mult=2.2,
                 min_level=12.0, window=0.35, sustain=0.10):
        self.jump_thr = min(max_jump, max(min_jump, mult * noise_rise))
        self.min_level, self.window, self.sustain = min_level, window, sustain
        self.hist = deque()
        self.pending = None            # (t_start, floor, jump)
        self.last_jump = 0.0

    def update(self, t, delta):
        """Feed one sample; returns True once a bite is confirmed."""
        while self.hist and t - self.hist[0][0] > self.window:
            self.hist.popleft()
        if self.pending:
            t0, floor, jump = self.pending
            if delta < floor + 0.5 * jump:
                self.pending = None                   # fell back: a glitch, not a bite
            elif t - t0 >= self.sustain:
                return True
            return False
        if self.hist:
            floor = min(x for _, x in self.hist)
            jump = delta - floor
            self.last_jump = max(self.last_jump, jump)
            if jump >= self.jump_thr and delta >= self.min_level:
                self.pending = (t, floor, jump)
                return False
        self.hist.append((t, delta))
        return False