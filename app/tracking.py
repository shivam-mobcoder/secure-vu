from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Tuple


class PIDTracker:
    def __init__(self, map_path: Path):
        self.map_path = map_path
        self.id_data: Dict[str, Any] = self._load_id_map()
        self.track_id_map: Dict[int, int] = {}
        self.pid_history: Dict[int, Dict[str, Any]] = {}

    def _load_id_map(self) -> Dict[str, Any]:
        if self.map_path.exists():
            try:
                return json.loads(self.map_path.read_text())
            except Exception:
                return {"next_id": 1, "map": {}}
        return {"next_id": 1, "map": {}}

    def _save_id_map(self) -> None:
        self.map_path.write_text(json.dumps(self.id_data, indent=2))

    def _allocate_pid(self) -> int:
        pid = self.id_data.get("next_id", 1)
        self.id_data["next_id"] = pid + 1
        self._save_id_map()
        return pid

    def _bbox_iou(self, box_a: Tuple[float, float, float, float], box_b: Tuple[float, float, float, float]) -> float:
        ax1, ay1, ax2, ay2 = box_a
        bx1, by1, bx2, by2 = box_b
        inter_x1 = max(ax1, bx1)
        inter_y1 = max(ay1, by1)
        inter_x2 = min(ax2, bx2)
        inter_y2 = min(ay2, by2)
        inter_w = max(0.0, inter_x2 - inter_x1)
        inter_h = max(0.0, inter_y2 - inter_y1)
        inter = inter_w * inter_h
        if inter <= 0:
            return 0.0
        area_a = max((ax2 - ax1) * (ay2 - ay1), 1.0)
        area_b = max((bx2 - bx1) * (by2 - by1), 1.0)
        union = area_a + area_b - inter
        return inter / union

    def _match_existing(self, bbox, timestamp: float, window: float) -> int | None:
        best_pid = None
        best_iou = 0.0
        for pid, data in self.pid_history.items():
            if data.get("active", False):
                continue
            if timestamp - data.get("last_seen", 0.0) > window:
                continue
            prev_box = data.get("bbox")
            if not prev_box:
                continue
            iou = self._bbox_iou(bbox, prev_box)
            if iou >= 0.35 and iou > best_iou:
                best_pid = pid
                best_iou = iou
        return best_pid

    def assign_pid(self, track_id: int, bbox, timestamp: float, window: float) -> int:
        pid = self.track_id_map.get(track_id)
        if pid is not None:
            return pid
        reused = self._match_existing(bbox, timestamp, window)
        if reused is not None:
            pid = reused
        else:
            pid = self._allocate_pid()
        self.track_id_map[track_id] = pid
        return pid

    def mark_active(self, pid: int, bbox, timestamp: float) -> None:
        self.pid_history[pid] = {"bbox": bbox, "last_seen": timestamp, "active": True}

    def sweep_inactive(self, current_track_ids) -> None:
        for tid in list(self.track_id_map.keys()):
            if tid not in current_track_ids:
                pid = self.track_id_map.pop(tid)
                if pid in self.pid_history:
                    self.pid_history[pid]["active"] = False
        active_pids = set(self.track_id_map.values())
        for pid, data in self.pid_history.items():
            if pid not in active_pids:
                data["active"] = False