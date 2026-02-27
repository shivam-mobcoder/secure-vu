from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

import numpy as np
from insightface.app import FaceAnalysis


class FaceIDManager:
    def __init__(self, db_path: Path, threshold: float = 0.45, ctx_id: int = 0):
        self.db_path = db_path
        self.threshold = threshold
        self.ctx_id = ctx_id
        self.app: Optional[FaceAnalysis] = None
        self.embeddings: Optional[np.ndarray] = None
        self.labels: Optional[np.ndarray] = None
        self.load()  # Load database immediately

    def load(self) -> None:
        if not self.db_path.exists():
            print(
                f"[FACE] No face_db.npz found at {self.db_path}. Face-ID will be disabled."
            )
            return
        # labels are stored as object dtype; allow_pickle needed to load safely
        # Some .npz files saved with newer NumPy versions may reference
        # numpy._core during pickling. Older NumPy builds (or different
        # installs) may not have that module path, causing ModuleNotFoundError
        # when unpickling. Provide a temporary sys.modules alias so pickle
        # can locate the actual numpy.core module.
        import sys

        # ensure any legacy/new NumPy module path used in pickles is available
        try:
            sys.modules.setdefault("numpy._core", np.core)
        except Exception:
            pass

        data = np.load(self.db_path, allow_pickle=True)
        try:
            self.embeddings = data["embeddings"]
            self.labels = data["labels"]
            self.embeddings[:] = self.embeddings / (
                np.linalg.norm(self.embeddings, axis=1, keepdims=True) + 1e-8
            )
        except Exception as e:
            print(f"[FACE] Failed to load face DB ({e}). Face-ID will be disabled.")
            return

        # Use local pretrained cache to avoid re-downloading
        root = Path(__file__).resolve().parent.parent / "pre_trained" / "insightface"
        try:
            ort_has_cuda_ep = False
            try:
                import onnxruntime as ort

                ort_has_cuda_ep = "CUDAExecutionProvider" in (
                    ort.get_available_providers() or []
                )
            except Exception:
                ort_has_cuda_ep = False

            prefer_cuda = (self.ctx_id >= 0) and ort_has_cuda_ep
            providers = (
                ["CUDAExecutionProvider", "CPUExecutionProvider"]
                if prefer_cuda
                else ["CPUExecutionProvider"]
            )
            try:
                self.app = FaceAnalysis(
                    name="buffalo_l", root=str(root), providers=providers
                )
            except Exception as e:
                # If CUDA provider fails (common on systems without a CUDA device), retry on CPU.
                self.app = FaceAnalysis(
                    name="buffalo_l", root=str(root), providers=["CPUExecutionProvider"]
                )
                self.ctx_id = -1
            self.app.prepare(ctx_id=self.ctx_id, det_size=(320, 320))
            print(
                f"[FACE] Loaded database with identities: {sorted(set(self.labels.tolist()))}"
            )
        except Exception as e:
            print(
                f"[FACE] Failed to initialize FaceAnalysis: {e}. Face-ID will be disabled."
            )
            self.app = None
            self.embeddings = None
            self.labels = None

    def recognize_batch(
        self,
        frame: np.ndarray,
        boxes: list,
    ) -> list:
        """
        Recognize ALL people in one GPU pass.

        Runs InsightFace on the FULL frame once, detects all faces, then
        matches each detected face back to the nearest YOLO bounding box.
        Returns a list of (name, score, embedding) tuples — one per input box,
        in the same order.  This is far more efficient than calling the model
        once per person because the GPU only needs one batched inference.

        Args:
            frame: full BGR frame (not a crop)
            boxes: list of (x1, y1, x2, y2) tuples from YOLO

        Returns:
            list of (name: str, score: float, emb: np.ndarray|None)
        """
        default = ("Unknown", 0.0, None)
        if self.app is None or self.embeddings is None or not boxes:
            return [default] * len(boxes)

        # Downscale frame for faster InsightFace detection (640px wide).
        # Full-res (1280×720) is very expensive; 640-wide is 3-4× faster
        # and still accurate for face detection.
        import cv2 as _cv2

        h, w = frame.shape[:2]
        MAX_FACE_W = 640
        if w > MAX_FACE_W:
            scale = MAX_FACE_W / w
            small_frame = _cv2.resize(frame, (MAX_FACE_W, int(h * scale)))
        else:
            scale = 1.0
            small_frame = frame

        # Run the full InsightFace pipeline on the downscaled frame — one GPU call.
        try:
            detected_faces = self.app.get(small_frame)
        except Exception:
            return [default] * len(boxes)

        if not detected_faces:
            return [default] * len(boxes)

        # Scale face bboxes back to original frame coordinates
        if scale != 1.0:
            for face in detected_faces:
                face.bbox = face.bbox / scale

        h, w = frame.shape[:2]

        # Helper: compute IoU between two boxes (x1,y1,x2,y2)
        def _iou(a, b):
            ax1, ay1, ax2, ay2 = a
            bx1, by1, bx2, by2 = b
            ix1 = max(ax1, bx1)
            iy1 = max(ay1, by1)
            ix2 = min(ax2, bx2)
            iy2 = min(ay2, by2)
            inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
            area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
            area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
            union = area_a + area_b - inter
            return inter / union if union > 0 else 0.0

        # For each YOLO box, find the InsightFace detection whose bbox center
        # falls inside the YOLO box (or has the highest IoU if none is inside).
        results = []
        for box in boxes:
            bx1, by1, bx2, by2 = (
                max(0, int(box[0])),
                max(0, int(box[1])),
                min(w - 1, int(box[2])),
                min(h - 1, int(box[3])),
            )
            if bx2 <= bx1 or by2 <= by1:
                results.append(default)
                continue

            best_face = None
            best_score = -1.0

            for face in detected_faces:
                fx1, fy1, fx2, fy2 = face.bbox
                cx = (fx1 + fx2) / 2
                cy = (fy1 + fy2) / 2
                # Primary: face center inside YOLO box (upper-half preferred)
                face_mid_y = by1 + (by2 - by1) * 0.55  # up to 55 % height covers head
                if bx1 <= cx <= bx2 and by1 <= cy <= face_mid_y:
                    iou = _iou((bx1, by1, bx2, by2), (fx1, fy1, fx2, fy2))
                    if iou > best_score:
                        best_score = iou
                        best_face = face

            # Fallback: best IoU regardless of center position
            if best_face is None:
                for face in detected_faces:
                    iou = _iou((bx1, by1, bx2, by2), tuple(face.bbox))
                    if iou > best_score:
                        best_score = iou
                        best_face = face

            if best_face is None or best_face.embedding is None:
                results.append(default)
                continue

            emb = best_face.embedding
            emb = emb / (np.linalg.norm(emb) + 1e-8)
            sims = self.embeddings @ emb  # type: ignore[operator]
            best_idx = int(np.argmax(sims))
            best_sim = float(sims[best_idx])

            if best_sim < self.threshold:
                results.append(("Unknown", best_sim, emb))
            else:
                results.append((str(self.labels[best_idx]), best_sim, emb))

        return results

    def recognize_with_embedding(
        self, frame, box: Tuple[int, int, int, int]
    ) -> Tuple[str, float, Optional[np.ndarray]]:
        # Single-box recognition — wraps recognize_batch for backward compat.
        results = self.recognize_batch(frame, [box])
        if not results:
            return "Unknown", 0.0, None
        return results[0]
