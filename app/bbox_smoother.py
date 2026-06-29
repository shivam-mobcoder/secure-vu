import math


class BBoxSmoother:
    def __init__(
        self,
        mode="fixed",
        fixed_alpha=0.75,
        alpha_high=0.30,
        alpha_medium=0.55,
        alpha_low=0.80,
        conf_high=0.85,
        conf_medium=0.60,
        jump_thresh=1.5,
    ):
        self.mode = mode.strip().lower()
        self.fixed_alpha = fixed_alpha
        self.alpha_high = alpha_high
        self.alpha_medium = alpha_medium
        self.alpha_low = alpha_low
        self.conf_high = conf_high
        self.conf_medium = conf_medium
        self.jump_thresh = float(jump_thresh)

    def get_alpha(self, confidence: float) -> float:
        if self.mode != "adaptive":
            return self.fixed_alpha

        if confidence >= self.conf_high:
            return self.alpha_high
        if confidence >= self.conf_medium:
            return self.alpha_medium
        return self.alpha_low

    def _center_jump(self, previous_box: tuple, current_box: tuple) -> float:
        px1, py1, px2, py2 = previous_box
        x1, y1, x2, y2 = current_box
        pw = max(1.0, px2 - px1)
        ph = max(1.0, py2 - py1)
        diag = math.hypot(pw, ph)
        cx_prev = (px1 + px2) * 0.5
        cy_prev = (py1 + py2) * 0.5
        cx_cur = (x1 + x2) * 0.5
        cy_cur = (y1 + y2) * 0.5
        return math.hypot(cx_cur - cx_prev, cy_cur - cy_prev) / diag

    def smooth(self, previous_box: tuple, current_box: tuple, confidence: float) -> tuple:
        if self._center_jump(previous_box, current_box) > self.jump_thresh:
            return current_box

        px1, py1, px2, py2 = previous_box
        x1, y1, x2, y2 = current_box
        alpha = self.get_alpha(confidence)

        sx1 = alpha * px1 + (1.0 - alpha) * x1
        sy1 = alpha * py1 + (1.0 - alpha) * y1
        sx2 = alpha * px2 + (1.0 - alpha) * x2
        sy2 = alpha * py2 + (1.0 - alpha) * y2

        return (sx1, sy1, sx2, sy2)
