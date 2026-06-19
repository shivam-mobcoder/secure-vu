"""MLflow experiment and deployment configuration tracking for SecureVu."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
TRACKING_DIR = REPO_ROOT / "tracking"
LAST_SNAPSHOT_FILE = TRACKING_DIR / "last_deployment_snapshot.json"

MLFLOW_ENABLE = os.getenv("MLFLOW_ENABLE", "1").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5000")
MLFLOW_EXPERIMENT_TRAINING = os.getenv(
    "MLFLOW_EXPERIMENT_TRAINING", "securevu-training"
)
MLFLOW_EXPERIMENT_DEPLOYMENT = os.getenv(
    "MLFLOW_EXPERIMENT_DEPLOYMENT", "securevu-deployment"
)
MLFLOW_MODEL_NAME = os.getenv("MLFLOW_MODEL_NAME", "securevu-person-detector")

# Keys that must never be logged (exact or suffix match).
REDACT_EXACT = frozenset(
    {
        "DB_PASS",
        "JWT_SECRET",
        "SUPER_PASSWORD",
        "ADMIN_PASSWORD",
        "MEMBER_PASSWORD",
    }
)
REDACT_PREFIXES = ("RTSP_URL",)

ML_CONFIG_KEYS = [
    "MODEL_SELECT",
    "MODEL_RUNTIME",
    "YOLO_WEIGHTS",
    "YOLO_PROCESS_EVERY_N_FRAMES",
    "YOLO_MIN_CONF",
    "YOLO_INPUT_WIDTH",
    "YOLO_INPUT_HEIGHT",
    "FOCUS_YOLO_INPUT_WIDTH",
    "FOCUS_YOLO_INPUT_HEIGHT",
    "YOLO_ENABLE_FP16",
    "YOLO_ENABLE_FUSE",
    "YOLO_TILING",
    "FACE_ENABLE",
    "FACE_EVERY_N_FRAMES",
    "FACE_RECOGNITION_THRESHOLD",
    "FACE_MIN_BBOX_HEIGHT",
    "MOTION_ENABLE",
    "MOTION_THRESH",
    "MOTION_ALERT_GAP_SEC",
    "MOTION_ONLY_WHEN_NO_PERSONS",
    "LINGER_SECONDS",
    "CONTINUOUS_RECORDING_ENABLE",
    "CONTINUOUS_SEGMENT_SECS",
    "PROCESSING_FPS",
    "SERVER_CAMERA_FPS",
    "GRID_CAMERA_FPS",
    "WORK_TIMER_ENABLE",
    "WORK_EMBED_MATCH_THRESHOLD",
    "BBOX_SMOOTHING_MODE",
    "BBOX_FIXED_ALPHA",
    "BBOX_ALPHA_HIGH",
    "BBOX_ALPHA_MEDIUM",
    "BBOX_ALPHA_LOW",
    "BBOX_CONF_HIGH",
    "BBOX_CONF_MEDIUM",
    "EVENT_CLIP_ENABLE",
    "ANALYTICS_ALL_CCTV",
    "ANALYTICS_CAMERA_IDS",
    "ALERT_LINE_ZONE_MIN_GAP",
    "ALERT_KNOWN_DETECT_MIN_GAP",
    "ALERT_UNKNOWN_ONCE_TTL_SEC",
    "BT_TRACK_LOW_THRESH",
    "PID_ENABLE",
    "PERF_STATS",
    "DISABLE_DRAWING",
    "POSTURE_ENABLE",
    "MLFLOW_ENABLE",
]

_PRODUCTION_WEIGHTS = {
    6: "models/yolo/secure_cv_best.pt",
    7: "models/yolo/secure_cv_best.pt",
    9: "models/yolo/secure_cv_best_l.pt",
    10: "models/yolo/secure_cv_best_x.pt",
    11: "models/yolo/secure_cv_best_l.pt",
    12: "models/yolo/secure_cv_best_x.pt",
}

_runtime_context: dict[str, Any] = {}
_context_lock = threading.Lock()


def set_runtime_context(**kwargs: Any) -> None:
    """Optional overrides from server after model load (weights path, runtime)."""
    with _context_lock:
        _runtime_context.update(kwargs)


def _mlflow_client():
    if not MLFLOW_ENABLE:
        return None
    try:
        import mlflow

        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        return mlflow
    except ImportError:
        logger.debug("mlflow package not installed; tracking disabled")
        return None
    except Exception as e:
        logger.warning("MLflow init failed: %s", e)
        return None


def _should_redact(key: str) -> bool:
    if key in REDACT_EXACT:
        return True
    return any(key.startswith(prefix) for prefix in REDACT_PREFIXES)


def _redact_value(key: str, value: str | None) -> str:
    if value is None:
        return ""
    if not _should_redact(key):
        return value
    if key.startswith("RTSP_URL") and value:
        try:
            parsed = urlparse(value)
            if parsed.hostname:
                return f"redacted://{parsed.hostname}/..."
        except Exception:
            pass
    return "redacted"


def snapshot_env_config() -> dict[str, str]:
    out: dict[str, str] = {}
    for key in ML_CONFIG_KEYS:
        raw = os.getenv(key)
        if raw is not None:
            out[key] = _redact_value(key, raw)
    for key, value in os.environ.items():
        if key.startswith("RTSP_URL_") and key not in out:
            out[key] = _redact_value(key, value)
    return out


def file_fingerprint(path: Path | str | None) -> dict[str, Any]:
    p = Path(path) if path else None
    if not p or not p.exists() or not p.is_file():
        return {"path": str(p) if p else "", "exists": False}
    try:
        data = p.read_bytes()
        return {
            "path": str(p),
            "exists": True,
            "sha256": hashlib.sha256(data).hexdigest(),
            "size_bytes": p.stat().st_size,
            "mtime_iso": datetime.fromtimestamp(p.stat().st_mtime).isoformat(),
        }
    except Exception as e:
        return {"path": str(p), "exists": False, "error": str(e)}


def _resolve_yolo_weights_path() -> Path:
    with _context_lock:
        ctx_path = _runtime_context.get("yolo_weights_path")
    if ctx_path:
        return Path(ctx_path)
    model_select = int(os.getenv("MODEL_SELECT", "6"))
    if model_select == 8:
        return REPO_ROOT / "models" / "yolo" / "yolov8s-worldv2.pt"
    if model_select in _PRODUCTION_WEIGHTS:
        return REPO_ROOT / _PRODUCTION_WEIGHTS[model_select]
    custom = os.getenv("YOLO_WEIGHTS")
    if custom:
        return Path(custom) if os.path.isabs(custom) else REPO_ROOT / custom
    return REPO_ROOT / "models" / "yolo" / "secure_cv_best.pt"


def snapshot_models() -> dict[str, Any]:
    weights = _resolve_yolo_weights_path()
    runtime = os.getenv("MODEL_RUNTIME", "pytorch")
    with _context_lock:
        runtime = _runtime_context.get("yolo_runtime", runtime)
    engine = weights.with_suffix(".engine")
    active = engine if runtime == "tensorrt" and engine.exists() else weights
    return {
        "yolo_weights": file_fingerprint(active),
        "yolo_weights_pt": file_fingerprint(weights),
        "face_db": file_fingerprint(
            REPO_ROOT / "models" / "arcface" / "face_db" / "face_db.npz"
        ),
        "camera_rules": file_fingerprint(REPO_ROOT / "config" / "camera_rules.json"),
        "runtime_flags": file_fingerprint(
            REPO_ROOT / "config" / "runtime_flags.json"
        ),
        "web_roi": file_fingerprint(REPO_ROOT / "models" / "roi" / "web_roi.json"),
    }


def get_git_metadata() -> dict[str, str]:
    meta: dict[str, str] = {}
    try:
        sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        meta["git_sha"] = sha
    except Exception:
        pass
    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=REPO_ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        meta["git_branch"] = branch
    except Exception:
        pass
    return meta


def _config_snapshot_dict(
    extra_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    snap = {
        "env": snapshot_env_config(),
        "models": snapshot_models(),
        "extra": extra_params or {},
    }
    with _context_lock:
        if _runtime_context:
            snap["runtime_context"] = dict(_runtime_context)
    return snap


def _snapshot_hash(snap: dict[str, Any]) -> str:
    payload = json.dumps(snap, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def compare_to_last_run(snap: dict[str, Any]) -> tuple[list[str], str]:
    """Return changed top-level env keys vs last saved snapshot."""
    current_hash = _snapshot_hash(snap)
    changed: list[str] = []
    try:
        if LAST_SNAPSHOT_FILE.exists():
            prev = json.loads(LAST_SNAPSHOT_FILE.read_text(encoding="utf-8"))
            prev_env = prev.get("env") or {}
            curr_env = snap.get("env") or {}
            for key in sorted(set(prev_env) | set(curr_env)):
                if prev_env.get(key) != curr_env.get(key):
                    changed.append(key)
    except Exception:
        pass
    return changed, current_hash


def _persist_snapshot(snap: dict[str, Any], run_hash: str) -> None:
    try:
        TRACKING_DIR.mkdir(parents=True, exist_ok=True)
        payload = {**snap, "snapshot_hash": run_hash, "saved_at": datetime.now().isoformat()}
        LAST_SNAPSHOT_FILE.write_text(
            json.dumps(payload, indent=2, default=str), encoding="utf-8"
        )
    except Exception as e:
        logger.debug("Could not persist deployment snapshot: %s", e)


def _log_params_flat(mlflow, params: dict[str, Any], prefix: str = "") -> None:
    for key, value in params.items():
        param_key = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"
        if isinstance(value, dict):
            _log_params_flat(mlflow, value, param_key)
        else:
            try:
                mlflow.log_param(param_key, str(value)[:500])
            except Exception:
                pass


def log_deployment_run(
    source: str = "server_startup",
    extra_params: dict[str, Any] | None = None,
    artifact_paths: list[str | Path] | None = None,
    metrics: dict[str, float] | None = None,
) -> str | None:
    """Log a full deployment configuration snapshot."""
    mlflow = _mlflow_client()
    if mlflow is None:
        return None
    snap = _config_snapshot_dict(extra_params)
    changed_keys, run_hash = compare_to_last_run(snap)
    git_meta = get_git_metadata()
    try:
        mlflow.set_experiment(MLFLOW_EXPERIMENT_DEPLOYMENT)
        run_name = f"deploy_{source}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        with mlflow.start_run(run_name=run_name) as run:
            mlflow.set_tag("source", source)
            mlflow.set_tag("snapshot_hash", run_hash)
            for k, v in git_meta.items():
                mlflow.set_tag(k, v)
            if changed_keys:
                mlflow.set_tag("changed_params", ",".join(changed_keys))
            _log_params_flat(mlflow, snap.get("env", {}))
            _log_params_flat(mlflow, snap.get("models", {}), prefix="models")
            if extra_params:
                _log_params_flat(mlflow, extra_params, prefix="extra")
            if metrics:
                for mk, mv in metrics.items():
                    try:
                        mlflow.log_metric(mk, float(mv))
                    except Exception:
                        pass
            yolo_fp = (snap.get("models") or {}).get("yolo_weights") or {}
            if yolo_fp.get("sha256"):
                mlflow.set_tag("weights_sha256", yolo_fp["sha256"])
            paths = list(artifact_paths or [])
            rules = REPO_ROOT / "config" / "camera_rules.json"
            if rules.exists() and str(rules) not in {str(p) for p in paths}:
                paths.append(rules)
            flags = REPO_ROOT / "config" / "runtime_flags.json"
            if flags.exists():
                paths.append(flags)
            for path in paths:
                p = Path(path)
                if p.exists():
                    try:
                        mlflow.log_artifact(str(p))
                    except Exception as e:
                        logger.debug("Artifact log failed for %s: %s", p, e)
            _maybe_register_deployment_weights(mlflow, yolo_fp)
            _persist_snapshot(snap, run_hash)
            logger.info("MLflow deployment run logged: %s (%s)", run.info.run_id, source)
            return run.info.run_id
    except Exception as e:
        logger.warning("MLflow deployment run failed: %s", e)
        return None


def log_config_change(
    source: str,
    changed_keys: list[str] | None = None,
    extra_params: dict[str, Any] | None = None,
    artifact_paths: list[str | Path] | None = None,
    metrics: dict[str, float] | None = None,
) -> str | None:
    """Log a lightweight run when runtime config changes (rules, toggles, face db)."""
    keys = changed_keys or []
    params = dict(extra_params or {})
    params["change_source"] = source
    if keys:
        params["changed_keys"] = ",".join(keys)
    return log_deployment_run(
        source=source,
        extra_params=params,
        artifact_paths=artifact_paths,
        metrics=metrics,
    )


def _maybe_register_deployment_weights(mlflow, yolo_fp: dict[str, Any]) -> None:
    """Register weights in Model Registry if SHA changed since last registry log."""
    sha = yolo_fp.get("sha256")
    path = yolo_fp.get("path")
    if not sha or not path or not Path(path).exists():
        return
    registry_marker = TRACKING_DIR / "last_registry_sha256.txt"
    try:
        prev_sha = registry_marker.read_text(encoding="utf-8").strip() if registry_marker.exists() else ""
        if prev_sha == sha:
            return
        version = register_yolo_model(Path(path), training_run_id=None, tags={"source": "deployment"})
        if version:
            registry_marker.write_text(sha, encoding="utf-8")
            mlflow.set_tag("registry_version", str(version))
    except Exception as e:
        logger.debug("Deployment registry check skipped: %s", e)


def register_yolo_model(
    weights_path: Path | str,
    training_run_id: str | None = None,
    tags: dict[str, str] | None = None,
) -> str | None:
    """Register YOLO weights as a new Model Registry version."""
    mlflow = _mlflow_client()
    if mlflow is None:
        return None
    path = Path(weights_path)
    if not path.exists():
        logger.warning("Cannot register missing weights: %s", path)
        return None
    try:
        from mlflow.tracking import MlflowClient

        client = MlflowClient()
        try:
            client.create_registered_model(MLFLOW_MODEL_NAME)
        except Exception:
            pass
        fp = file_fingerprint(path)
        version_tags = {
            "sha256": fp.get("sha256", ""),
            "weights_path": str(path),
            "registered_at": datetime.now().isoformat(),
        }
        if tags:
            version_tags.update(tags)
        if training_run_id:
            version_tags["training_run_id"] = training_run_id
            model_uri = f"runs:/{training_run_id}/weights/best.pt"
            result = mlflow.register_model(model_uri=model_uri, name=MLFLOW_MODEL_NAME)
        else:
            with mlflow.start_run(
                run_name=f"registry_{path.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            ) as run:
                mlflow.log_artifact(str(path), artifact_path="weights")
                for k, v in version_tags.items():
                    mlflow.set_tag(k, v)
                model_uri = f"runs:/{run.info.run_id}/weights/{path.name}"
                result = mlflow.register_model(
                    model_uri=model_uri, name=MLFLOW_MODEL_NAME
                )
        version = getattr(result, "version", None)
        if version is not None:
            client.set_registered_model_tag(
                MLFLOW_MODEL_NAME, "latest_sha256", fp.get("sha256", "")
            )
        logger.info("Registered model %s version %s", MLFLOW_MODEL_NAME, version)
        return str(version) if version is not None else None
    except Exception as e:
        logger.warning("Model registry failed: %s", e)
        return None


def log_training_run(
    params: dict[str, Any],
    metrics: dict[str, float],
    artifact_paths: list[str | Path],
    run_name: str | None = None,
) -> str | None:
    """Log a training experiment run."""
    mlflow = _mlflow_client()
    if mlflow is None:
        return None
    try:
        mlflow.set_experiment(MLFLOW_EXPERIMENT_TRAINING)
        name = run_name or f"train_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        with mlflow.start_run(run_name=name) as run:
            for k, v in params.items():
                try:
                    mlflow.log_param(k, v)
                except Exception:
                    pass
            for k, v in metrics.items():
                try:
                    mlflow.log_metric(k, float(v))
                except Exception:
                    pass
            for git_k, git_v in get_git_metadata().items():
                mlflow.set_tag(git_k, git_v)
            for path in artifact_paths:
                p = Path(path)
                if p.exists():
                    try:
                        if p.is_dir():
                            mlflow.log_artifacts(str(p))
                        else:
                            mlflow.log_artifact(str(p))
                    except Exception as e:
                        logger.debug("Training artifact skip %s: %s", p, e)
            return run.info.run_id
    except Exception as e:
        logger.warning("MLflow training run failed: %s", e)
        return None


def schedule_tracking(callback, *args, **kwargs) -> None:
    """Fire-and-forget tracking from sync code (rules save, face enroll)."""

    def _run():
        try:
            callback(*args, **kwargs)
        except Exception as e:
            logger.debug("Background MLflow task failed: %s", e)

    threading.Thread(target=_run, daemon=True, name="mlflow-track").start()
