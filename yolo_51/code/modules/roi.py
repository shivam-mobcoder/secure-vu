
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Sequence, Set, Tuple

import cv2
import numpy as np
import yaml


@dataclass
class ROIZone:
    name: str
    points: Sequence[Tuple[float, float]]
    classes: frozenset[str]
    cooldown: float
    normalized: bool = False
    color: Tuple[int, int, int] = (0, 255, 255)
    alpha: float = 0.15
    _last_alert: Dict[str, float] = field(default_factory=dict)

    def polygon_for_frame(self, width: int, height: int) -> np.ndarray:
        if self.normalized:
            scaled = [(x * width, y * height) for x, y in self.points]
        else:
            scaled = self.points
        return np.array([(int(x), int(y)) for x, y in scaled], dtype=np.int32)

    def contains(self, cx: float, cy: float, polygon: np.ndarray, margin: float = 0.0) -> bool:
        if polygon.size == 0:
            return False
        dist = cv2.pointPolygonTest(polygon.astype(np.float32), (float(cx), float(cy)), True)
        return bool(dist >= margin)

    def allows(self, label: str) -> bool:
        return not self.classes or label in self.classes

    def should_alert(self, key: str, timestamp: float) -> bool:
        last = self._last_alert.get(key, float("-inf"))
        if timestamp - last < self.cooldown:
            return False
        self._last_alert[key] = timestamp
        return True


def load_roi_zones(path: Path) -> List[ROIZone]:
    if not path.exists():
        print(f"[ROI] Config not found at {path}. Running without tripwires.")
        return []

    data = yaml.safe_load(path.read_text()) or {}
    zones_cfg = data.get("zones", [])
    default_cooldown = float(data.get("default_cooldown", 3.0))
    default_alpha = float(data.get("default_alpha", 0.15))
    zones: List[ROIZone] = []

    for idx, cfg in enumerate(zones_cfg):
        raw_points = cfg.get("polygon")
        if not raw_points or len(raw_points) < 3:
            print(f"[ROI] Skipping zone #{idx} (needs >=3 points)")
            continue

        points: List[Tuple[float, float]] = [(float(x), float(y)) for x, y in raw_points]
        normalized = bool(cfg.get("normalized", False))
        classes = frozenset(cfg.get("classes") or [])
        cooldown = float(cfg.get("cooldown", default_cooldown))
        color_cfg = cfg.get("color")

        if isinstance(color_cfg, (list, tuple)) and len(color_cfg) == 3:
            color = tuple(int(c) for c in color_cfg)
        else:
            color = (0, 255, 255)

        alpha = float(cfg.get("alpha", default_alpha))

        zones.append(
            ROIZone(
                name=cfg.get("name", f"zone_{idx}"),
                points=points,
                classes=classes,
                cooldown=cooldown,
                normalized=normalized,
                color=color,
                alpha=alpha,
            )
        )

    if not zones:
        print("[ROI] No valid zones defined; alerts disabled.")
    return zones


def draw_zones(frame: np.ndarray, zones: Sequence[ROIZone], polygons: Dict[str, np.ndarray], highlight: Set[str], show: bool) -> None:
    if not show or not zones:
        return

    overlay = frame.copy()
    for zone in zones:
        poly = polygons.get(zone.name)
        if poly is None or poly.size == 0:
            continue

        base_color = zone.color if zone.name not in highlight else (0, 0, 255)
        cv2.fillPoly(overlay, [poly], base_color)
        cv2.polylines(frame, [poly], True, base_color, 2)

    alpha = max(zone.alpha for zone in zones) if zones else 0.15
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)


def polygon_bbox_intersection_area(poly: np.ndarray, box: Tuple[float, float, float, float]) -> float:
    l, t, r, b = box
    bbox_poly = np.array([[l, t], [r, t], [r, b], [l, b]], dtype=np.float32)
    zone_poly = cv2.convexHull(poly.astype(np.float32))
    bbox_poly = cv2.convexHull(bbox_poly)
    area, _ = cv2.intersectConvexConvex(zone_poly, bbox_poly)
    return float(area) if area is not None else 0.0


def interactive_draw_roi_on_frame(frame: np.ndarray, save_path: Path) -> bool:
    h, w = frame.shape[:2]
    size = min(h, w) // 3
    cx, cy = w // 2, h // 2
    half = max(size // 2, 60)
    l, t, r, b = cx - half, cy - half, cx + half, cy + half

    window = "Adjust ROI (drag corners to resize, drag inside to move; s=save+exit, c=reset, q=close)"

    mode: str | int | None = None  # 'move' or corner idx 0..3
    drag_start: tuple[int, int] | None = None
    move_offset: tuple[int, int] | None = None
    corner_radius = 14
    min_size = 20

    def corners_from_rect(box: tuple[int, int, int, int]) -> list[tuple[int, int]]:
        l, t, r, b = box
        return [(l, t), (r, t), (r, b), (l, b)]

    def clamp_box(box: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        l, t, r, b = box
        l = max(0, min(w - 1, l))
        t = max(0, min(h - 1, t))
        r = max(l + 1, min(w - 1, r))
        b = max(t + 1, min(h - 1, b))
        return l, t, r, b

    def normalize_box(box: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
        l, t, r, b = box
        if r < l:
            l, r = r, l
        if b < t:
            t, b = b, t
        return l, t, r, b

    def point_near(px: int, py: int, pt: tuple[int, int]) -> bool:
        return abs(px - pt[0]) <= corner_radius and abs(py - pt[1]) <= corner_radius

    def on_mouse(event, x, y, _flags, _param):
        nonlocal mode, drag_start, move_offset, l, t, r, b
        if event == cv2.EVENT_LBUTTONDOWN:
            # Corner hit-test (LT, RT, RB, LB)
            for idx, pt in enumerate(corners_from_rect((l, t, r, b))):
                if point_near(x, y, pt):
                    mode = idx
                    drag_start = (x, y)
                    return
            # Inside move
            if l <= x <= r and t <= y <= b:
                mode = "move"
                drag_start = (x, y)
                move_offset = (x - l, y - t)
        elif event == cv2.EVENT_MOUSEMOVE and mode is not None:
            if mode == "move" and drag_start and move_offset:
                dx = x - drag_start[0]
                dy = y - drag_start[1]
                new_l = l + dx
                new_t = t + dy
                width = r - l
                height = b - t
                new_l = max(0, min(w - width, new_l))
                new_t = max(0, min(h - height, new_t))
                l, t, r, b = new_l, new_t, new_l + width, new_t + height
                drag_start = (x, y)
            elif isinstance(mode, int):
                # Corner drag
                if mode == 0:  # LT
                    l, t = x, y
                elif mode == 1:  # RT
                    r, t = x, y
                elif mode == 2:  # RB
                    r, b = x, y
                elif mode == 3:  # LB
                    l, b = x, y
                l, t, r, b = normalize_box((l, t, r, b))
                if r - l < min_size:
                    if mode in (0, 3):
                        l = r - min_size
                    else:
                        r = l + min_size
                if b - t < min_size:
                    if mode in (0, 1):
                        t = b - min_size
                    else:
                        b = t + min_size
                l, t, r, b = clamp_box((l, t, r, b))
        elif event == cv2.EVENT_LBUTTONUP:
            mode = None
            drag_start = None
            move_offset = None

    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(window, on_mouse)

    saved_any = False
    while True:
        corners = corners_from_rect((l, t, r, b))
        display = frame.copy()
        poly = np.array(corners, dtype=np.int32)
        cv2.polylines(display, [poly], True, (0, 0, 255), 2)
        for idx, (px, py) in enumerate(corners):
            cv2.circle(display, (px, py), 6, (0, 255, 255), -1)
            cv2.putText(display, str(idx + 1), (px + 6, py - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)

        cv2.imshow(window, display)
        key = cv2.waitKey(10) & 0xFF
        if key == ord("q"):
            break
        if key == ord("c"):
            l, t, r, b = cx - half, cy - half, cx + half, cy + half
        if key in (ord("s"), ord("S"), 13):  # save on s or Enter
            data = {
                "default_cooldown": 3.0,
                "default_alpha": 0.15,
                "zones": [
                    {
                        "name": "drawn_zone",
                        "polygon": [[int(x), int(y)] for x, y in corners_from_rect((l, t, r, b))],
                        "classes": [],
                        "cooldown": 3.0,
                        "color": [0, 255, 255],
                        "alpha": 0.2,
                        "normalized": False,
                    }
                ],
            }
            save_path.parent.mkdir(parents=True, exist_ok=True)
            save_path.write_text(yaml.safe_dump(data))
            print(f"[ROI] Saved polygon to {save_path}")
            saved_any = True
            break

    cv2.destroyWindow(window)
    return saved_any


def interactive_draw_roi(source, save_path: Path) -> bool:
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        print("[ROI] Could not open source for drawing.")
        return False

    ok, base = cap.read()
    if not ok:
        print("[ROI] Failed to read frame for drawing.")
        cap.release()
        return False

    result = interactive_draw_roi_on_frame(base, save_path)
    cap.release()
    return result