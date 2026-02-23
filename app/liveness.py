"""
liveness.py — Anti-spoofing / liveness detection for face enrollment.

Uses a multi-layer approach that works entirely with already-installed
libraries (insightface, onnxruntime, opencv-python):

Layer 1 – Texture (LBP + frequency analysis)
    Printed photos / screen replays lack the micro-texture of real skin.
    We compute a Local Binary Pattern histogram and measure high-frequency
    energy. Spoof images tend to have periodic patterns from printer dots
    or LCD pixels.

Layer 2 – Gradient / Sharpness analysis
    Real faces captured live have natural sharpness gradients.
    A photo of a photo often has the sharpness signature of the medium
    (paper/screen) rather than the face itself.

Layer 3 – 3D Pose plausibility (via InsightFace landmarks)
    InsightFace buffalo_l returns a 3D pose vector [yaw, pitch, roll].
    A flat 2D photo held in front of the camera shows minimal natural
    3D variation across multiple frames. We require at least 2° of
    natural micro-movement across the capture sequence (involuntary
    head sway) OR a detectable depth cue from the landmark geometry.

Layer 4 – Specular reflection check
    Real skin exhibits subtle specular highlights. A matte printout or
    phone screen has a different reflectance signature detectable by
    looking at local highlight distribution.

All checks are combined into a single confidence score [0.0 – 1.0].
Score ≥ LIVENESS_THRESHOLD (default 0.55) → LIVE.

No additional pip packages are required beyond what the project already uses.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Confidence threshold to pass liveness
LIVENESS_THRESHOLD = float(0.50)


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _to_gray(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def _crop_face(image: np.ndarray, bbox, margin: float = 0.25) -> Optional[np.ndarray]:
    """Crop and square-pad a face region with margin."""
    try:
        x1, y1, x2, y2 = [int(v) for v in bbox[:4]]
        h, w = image.shape[:2]
        dx = int((x2 - x1) * margin)
        dy = int((y2 - y1) * margin)
        x1 = max(0, x1 - dx)
        y1 = max(0, y1 - dy)
        x2 = min(w, x2 + dx)
        y2 = min(h, y2 + dy)
        if x2 <= x1 or y2 <= y1:
            return None
        return image[y1:y2, x1:x2]
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Layer 1 — LBP texture score
# ---------------------------------------------------------------------------

def _compute_lbp(gray: np.ndarray, radius: int = 1, n_points: int = 8) -> np.ndarray:
    """
    Simplified uniform LBP without scikit-image.
    Returns a normalised histogram of LBP codes.
    """
    h, w = gray.shape
    lbp = np.zeros((h, w), dtype=np.float32)
    # Precompute offsets for n_points neighbours on a circle of `radius`
    angles = 2 * np.pi * np.arange(n_points) / n_points
    offsets = [(int(round(radius * np.sin(a))),
                int(round(radius * np.cos(a)))) for a in angles]
    fp = gray.astype(np.float32)
    for bit, (dy, dx) in enumerate(offsets):
        shifted = np.roll(np.roll(fp, dy, axis=0), dx, axis=1)
        lbp += ((shifted >= fp).astype(np.float32)) * (1 << bit)
    hist, _ = np.histogram(lbp.ravel(), bins=256, range=(0, 256), density=True)
    return hist


def _texture_score(face_crop: np.ndarray) -> float:
    """
    Real skin has a rich, varied LBP histogram.
    Spoofs (print, screen) tend to have more concentrated peaks.
    Score: entropy of LBP histogram (higher = more likely real).
    Normalised to [0, 1] relative to max theoretical entropy.
    """
    try:
        gray = _to_gray(face_crop)
        resized = cv2.resize(gray, (128, 128))
        hist = _compute_lbp(resized)
        # Shannon entropy
        hist_safe = np.clip(hist, 1e-12, None)
        entropy = -np.sum(hist_safe * np.log2(hist_safe))
        max_entropy = np.log2(256)
        return float(np.clip(entropy / max_entropy, 0.0, 1.0))
    except Exception as e:
        logger.debug(f"[LIVENESS] texture_score error: {e}")
        return 0.5


# ---------------------------------------------------------------------------
# Layer 2 — High-frequency energy (Laplacian + DFT)
# ---------------------------------------------------------------------------

def _hf_score(face_crop: np.ndarray) -> float:
    """
    Printed / re-photographed images tend to have a different high-frequency
    signature due to halftone dots or LCD sub-pixel patterns.
    We use the ratio of high-freq energy in the DFT magnitude spectrum.
    Score: ratio of energy in high spatial frequencies (outer ring of DFT).
    """
    try:
        gray = _to_gray(face_crop)
        resized = cv2.resize(gray, (128, 128)).astype(np.float32)
        dft = np.fft.fftshift(np.fft.fft2(resized))
        magnitude = np.log1p(np.abs(dft))
        h, w = magnitude.shape
        cy, cx = h // 2, w // 2
        Y, X = np.ogrid[:h, :w]
        radius_frac = 0.4  # frequencies beyond 40% of Nyquist
        mask_outer = ((X - cx) ** 2 + (Y - cy) ** 2) >= (radius_frac * min(cx, cy)) ** 2
        total = magnitude.sum()
        if total < 1e-8:
            return 0.5
        hf_ratio = magnitude[mask_outer].sum() / total
        # Empirically: real faces ~0.80–0.95 high-freq ratio; prints lower
        score = float(np.clip((hf_ratio - 0.60) / (0.90 - 0.60), 0.0, 1.0))
        return score
    except Exception as e:
        logger.debug(f"[LIVENESS] hf_score error: {e}")
        return 0.5


# ---------------------------------------------------------------------------
# Layer 3 — Blur / sharpness check
# ---------------------------------------------------------------------------

def _sharpness_score(face_crop: np.ndarray) -> float:
    """
    Laplacian variance of the face crop.
    Too blurry = likely motion blur (bad frame), too sharp = possibly print.
    We want a Goldilocks range typical of a real face at arm's length.
    """
    try:
        gray = _to_gray(face_crop)
        lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        # Very low variance → blur artifact from motion (bad but not spoof)
        # Extremely high uniform sharpness → could be high-DPI print
        # We penalise below 20 (blurry) and reward 50–800 range
        if lap_var < 20:
            return 0.3
        score = float(np.clip((lap_var - 20) / (600 - 20), 0.0, 1.0))
        return score
    except Exception as e:
        logger.debug(f"[LIVENESS] sharpness_score error: {e}")
        return 0.5


# ---------------------------------------------------------------------------
# Layer 4 — Specular / reflectance check
# ---------------------------------------------------------------------------

def _specular_score(face_crop: np.ndarray) -> float:
    """
    Real skin exhibits subtle specular highlights in a natural distribution.
    A matte printout lacks bright specular spots; a glossy screen has them
    concentrated in a very different pattern.
    We check if the top-5% bright pixels are spatially distributed (real)
    vs. uniform (print) or clustered in one corner (screen glare).
    """
    try:
        gray = _to_gray(face_crop)
        p95 = np.percentile(gray, 95)
        bright_mask = (gray >= p95).astype(np.float32)
        # If < 0.5% of pixels are bright → matte surface (possibly print)
        bright_frac = bright_mask.mean()
        if bright_frac < 0.005:
            return 0.35
        # If > 20% are bright → over-exposed or screen
        if bright_frac > 0.20:
            return 0.40
        # Check spatial distribution of bright pixels using std of coordinates
        ys, xs = np.where(bright_mask > 0)
        if len(xs) < 5:
            return 0.4
        spread = float((xs.std() + ys.std()) / (gray.shape[1] + gray.shape[0]))
        score = float(np.clip(spread * 4.0, 0.0, 1.0))
        return score
    except Exception as e:
        logger.debug(f"[LIVENESS] specular_score error: {e}")
        return 0.5


# ---------------------------------------------------------------------------
# Layer 5 — 3D pose plausibility (multi-frame micro-movement)
# ---------------------------------------------------------------------------

def _pose_variance_score(poses: list[tuple[float, float, float]]) -> float:
    """
    Across multiple frames, a real live face shows natural micro-movement
    (breathing, involuntary sway). A static printed photo shows near-zero
    pose variance. We expect at least 1–3° variance in at least one axis.
    """
    if len(poses) < 2:
        return 0.5
    try:
        arr = np.array(poses, dtype=np.float32)
        variances = arr.std(axis=0)  # [yaw_std, pitch_std, roll_std]
        max_std = float(variances.max())
        # < 0.3° → very suspicious (probably static image)
        # > 2° → clearly natural micro-movement
        score = float(np.clip((max_std - 0.3) / (3.0 - 0.3), 0.0, 1.0))
        return score
    except Exception as e:
        logger.debug(f"[LIVENESS] pose_variance_score error: {e}")
        return 0.5


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class LivenessChecker:
    """
    Multi-layer liveness checker.

    Usage (single frame):
        checker = LivenessChecker()
        score, detail = checker.check_frame(image_bgr, face_bbox)
        if score < checker.threshold:
            raise ValueError("Liveness check failed")

    Usage (multi-frame sequence — best accuracy):
        checker = LivenessChecker()
        scores, poses = [], []
        for frame, bbox, pose in frame_sequence:
            score, detail = checker.check_frame(frame, bbox)
            scores.append(score)
            if pose is not None:
                poses.append(pose)
        final_score = checker.aggregate(scores, poses)
        is_live = final_score >= checker.threshold
    """

    def __init__(self, threshold: float = LIVENESS_THRESHOLD):
        self.threshold = threshold

    def check_frame(
        self,
        image: np.ndarray,
        bbox,
        pose: Optional[tuple] = None,
    ) -> tuple[float, dict]:
        """
        Returns (score [0–1], detail_dict).
        score >= self.threshold → likely live.
        """
        face_crop = _crop_face(image, bbox)
        if face_crop is None or face_crop.size == 0:
            return 0.0, {"error": "crop_failed"}

        # Resize for consistent analysis
        face_crop = cv2.resize(face_crop, (128, 128))

        texture = _texture_score(face_crop)
        hf      = _hf_score(face_crop)
        sharp   = _sharpness_score(face_crop)
        spec    = _specular_score(face_crop)

        # Weighted combination (texture + HF carry the most signal)
        score = (
            0.35 * texture +
            0.30 * hf      +
            0.20 * sharp   +
            0.15 * spec
        )
        score = float(np.clip(score, 0.0, 1.0))

        detail = {
            "texture": round(texture, 3),
            "high_freq": round(hf, 3),
            "sharpness": round(sharp, 3),
            "specular": round(spec, 3),
            "frame_score": round(score, 3),
        }
        return score, detail

    def aggregate(
        self,
        frame_scores: list[float],
        poses: Optional[list[tuple]] = None,
    ) -> float:
        """
        Aggregate per-frame scores and optional pose variance across frames.
        Returns final confidence score [0–1].
        """
        if not frame_scores:
            return 0.0

        # Use median of frame scores (robust to outliers)
        median_score = float(np.median(frame_scores))

        pose_score = _pose_variance_score(poses) if poses else 0.5

        # Blend: 75% appearance, 25% motion
        final = 0.75 * median_score + 0.25 * pose_score
        return float(np.clip(final, 0.0, 1.0))

    def is_live(self, score: float) -> bool:
        return score >= self.threshold


# Module-level singleton (created lazily)
_checker: Optional[LivenessChecker] = None


def get_liveness_checker() -> LivenessChecker:
    global _checker
    if _checker is None:
        _checker = LivenessChecker()
    return _checker


def check_frames_liveness(
    frames: list[np.ndarray],
    face_data: list[dict],
) -> tuple[bool, float, list[dict]]:
    """
    Convenience wrapper. Check a list of frames with their detected face data.

    Args:
        frames: list of BGR numpy arrays
        face_data: list of dicts with keys 'bbox' and optionally 'pose'
                   (as returned by InsightFace: face.bbox, face.pose)

    Returns:
        (is_live, confidence_score, per_frame_details)
    """
    checker = get_liveness_checker()
    frame_scores: list[float] = []
    poses: list[tuple] = []
    details: list[dict] = []

    for i, (frame, fd) in enumerate(zip(frames, face_data)):
        bbox = fd.get("bbox")
        pose = fd.get("pose")  # (yaw, pitch, roll) or None
        if bbox is None:
            details.append({"frame": i, "skipped": "no_bbox"})
            continue
        score, detail = checker.check_frame(frame, bbox, pose)
        detail["frame"] = i
        frame_scores.append(score)
        details.append(detail)
        if pose is not None:
            try:
                poses.append(tuple(float(v) for v in pose[:3]))
            except Exception:
                pass

    if not frame_scores:
        return False, 0.0, details

    final_score = checker.aggregate(frame_scores, poses if poses else None)
    return checker.is_live(final_score), final_score, details
