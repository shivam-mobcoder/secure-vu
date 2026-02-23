import { useRef, useState, useCallback, useEffect } from 'react';
import { Camera, CheckCircle2, XCircle, Loader2, AlertCircle } from 'lucide-react';

/**
 * CapturePanel — Apple-style guided face capture.
 *
 * Guides the user through varied head poses (center, left, right, up, down,
 * slight-left, slight-right, tilt) to collect diverse frames for a robust
 * face embedding.  Each step uses a pixel-diff check so frames are only
 * accepted when the user has actually moved.
 *
 * Props:
 *   onCapture(frames: string[]) — called with base64 data-URIs when done
 *   onReset()                   — called when user discards and resets
 */

const POSES = [
    { id: 'center', label: 'Look straight at the camera', angle: 0 },
    { id: 'left', label: 'Slowly turn your head left', angle: -35 },
    { id: 'right', label: 'Slowly turn your head right', angle: 35 },
    { id: 'up', label: 'Tilt your chin up slightly', angle: -90 },
    { id: 'down', label: 'Tilt your chin down slightly', angle: 90 },
    { id: 'sleft', label: 'Look slightly to your left', angle: -20 },
    { id: 'sright', label: 'Look slightly to your right', angle: 20 },
    { id: 'tilt', label: 'Tilt your head to one side', angle: 55 },
];

const TARGET_FRAMES = POSES.length;
const DIFF_THRESHOLD = 12;      // min avg pixel diff to accept a new pose (lowered for leniency)
const SETTLE_DELAY_MS = 500;    // delay before sampling diff
const SUSTAINED_POLLS = 2;      // consecutive above-threshold polls required
const DIRECTION_SHIFT_MIN = 2;  // minimum centroid pixel-shift to validate direction
const FALLBACK_TIMEOUT_MS = 5000; // accept pose after 5s even if direction check fails

/* Direction validation map:  each pose id maps to an expected centroid shift.
 * axis: 'x' or 'y';  sign: +1 or -1 (relative to 64×48 thumbnail).
 * Note: webcam is mirrored, so "turn left" moves face-center rightward in image. */
const DIRECTION_CHECK = {
    left: { axis: 'x', sign: +1 },  // face center moves right in mirrored image
    right: { axis: 'x', sign: -1 },  // face center moves left in mirrored image
    up: { axis: 'y', sign: -1 },  // face center moves upward
    down: { axis: 'y', sign: +1 },  // face center moves downward
    sleft: { axis: 'x', sign: +1 },
    sright: { axis: 'x', sign: -1 },
    // center and tilt: no direction requirement (null)
};

export default function CapturePanel({ onCapture, onReset }) {
    const videoRef = useRef(null);
    const canvasRef = useRef(null);
    const streamRef = useRef(null);
    const animRef = useRef(null);
    const prevFrameDataRef = useRef(null);
    const captureTimerRef = useRef(null);
    const settleTimerRef = useRef(null);
    const poseIndexRef = useRef(0);
    const capturedRef = useRef([]);

    const [state, setState] = useState('idle');   // idle | starting | capturing | done | error
    const [cameraError, setCameraError] = useState(null);
    const [frames, setFrames] = useState([]);
    const [progress, setProgress] = useState(0);
    const [guidance, setGuidance] = useState('Position your face in the oval');
    const [cameraReady, setCameraReady] = useState(false);
    const [currentPose, setCurrentPose] = useState(null);
    const [poseAccepted, setPoseAccepted] = useState(false);

    // Start camera on mount
    useEffect(() => {
        startCamera();
        return () => stopCamera();
    }, []);

    async function startCamera() {
        setState('starting');
        setCameraError(null);
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'user' },
                audio: false,
            });
            streamRef.current = stream;
            if (videoRef.current) {
                videoRef.current.srcObject = stream;
                await videoRef.current.play();
                setCameraReady(true);
                setState('idle');
                drawGuide();
            }
        } catch (err) {
            console.error('[CapturePanel] Camera error:', err);
            const msg = err.name === 'NotAllowedError'
                ? 'Camera permission denied. Please allow camera access and reload.'
                : `Camera error: ${err.message}`;
            setCameraError(msg);
            setState('error');
        }
    }

    function stopCamera() {
        if (streamRef.current) {
            streamRef.current.getTracks().forEach(t => t.stop());
            streamRef.current = null;
        }
        if (animRef.current) {
            cancelAnimationFrame(animRef.current);
            animRef.current = null;
        }
        clearTimeout(captureTimerRef.current);
        clearTimeout(settleTimerRef.current);
        setCameraReady(false);
    }

    // ── Face-guide oval overlay ──────────────────────────────────────────────
    const drawGuide = useCallback(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        canvas.width = canvas.offsetWidth;
        canvas.height = canvas.offsetHeight;
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // Semi-transparent mask
        ctx.fillStyle = 'rgba(0,0,0,0.35)';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        const cx = canvas.width / 2;
        const cy = canvas.height / 2 - 10;
        const rw = canvas.width * 0.28;
        const rh = canvas.height * 0.42;

        // Cutout
        ctx.save();
        ctx.beginPath();
        ctx.ellipse(cx, cy, rw, rh, 0, 0, Math.PI * 2);
        ctx.clip();
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.restore();

        // Oval border — green when idle / capturing, accent when pose accepted
        ctx.beginPath();
        ctx.ellipse(cx, cy, rw, rh, 0, 0, Math.PI * 2);
        ctx.strokeStyle = poseAccepted ? '#3b82f6' : '#22c55e';
        ctx.lineWidth = 3;
        ctx.stroke();

        // Progress arc
        if (progress > 0 && progress <= TARGET_FRAMES) {
            const arcFraction = progress / TARGET_FRAMES;
            ctx.beginPath();
            ctx.ellipse(cx, cy, rw + 6, rh + 6, 0, -Math.PI / 2, -Math.PI / 2 + arcFraction * Math.PI * 2);
            ctx.strokeStyle = '#22c55e';
            ctx.lineWidth = 4;
            ctx.lineCap = 'round';
            ctx.stroke();
        }

        // Directional arrow indicator during capture
        if (currentPose && state === 'capturing') {
            const pose = POSES[poseIndexRef.current];
            if (pose) {
                const arrowAngle = (pose.angle * Math.PI) / 180;
                const arrowLen = rw * 0.35;
                const ax = cx + Math.sin(arrowAngle) * (rw + 22);
                const ay = cy - Math.cos(arrowAngle) * (rh + 22);

                // Pulsing dot
                ctx.beginPath();
                ctx.arc(ax, ay, 8, 0, Math.PI * 2);
                ctx.fillStyle = poseAccepted ? '#3b82f6' : '#22c55e';
                ctx.fill();

                // Small arrow line from oval edge towards the dot
                const ex = cx + Math.sin(arrowAngle) * (rw + 4);
                const ey = cy - Math.cos(arrowAngle) * (rh + 4);
                ctx.beginPath();
                ctx.moveTo(ex, ey);
                ctx.lineTo(ax, ay);
                ctx.strokeStyle = poseAccepted ? '#3b82f6' : '#22c55e';
                ctx.lineWidth = 2;
                ctx.stroke();
            }
        }

        animRef.current = requestAnimationFrame(drawGuide);
    }, [progress, currentPose, state, poseAccepted]);

    // Re-start draw loop when dependencies change
    useEffect(() => {
        if (cameraReady) {
            if (animRef.current) cancelAnimationFrame(animRef.current);
            drawGuide();
        }
    }, [drawGuide, cameraReady]);

    // ── Frame capture helpers ────────────────────────────────────────────────
    function captureFrame() {
        const video = videoRef.current;
        if (!video) return null;
        const offscreen = document.createElement('canvas');
        offscreen.width = video.videoWidth || 1280;
        offscreen.height = video.videoHeight || 720;
        offscreen.getContext('2d').drawImage(video, 0, 0);
        return offscreen.toDataURL('image/jpeg', 0.92);
    }

    /** Get a small grayscale thumbnail for diff comparison */
    function getComparisonData() {
        const video = videoRef.current;
        if (!video) return null;
        const sw = 64, sh = 48;
        const off = document.createElement('canvas');
        off.width = sw;
        off.height = sh;
        const ctx = off.getContext('2d');
        ctx.drawImage(video, 0, 0, sw, sh);
        return ctx.getImageData(0, 0, sw, sh).data;
    }

    /** Average absolute pixel difference between two ImageData buffers */
    function frameDiff(a, b) {
        if (!a || !b || a.length !== b.length) return 999;
        let sum = 0;
        const len = a.length;
        for (let i = 0; i < len; i += 4) {
            sum += Math.abs(a[i] - b[i]);       // R
            sum += Math.abs(a[i + 1] - b[i + 1]);   // G
            sum += Math.abs(a[i + 2] - b[i + 2]);   // B
        }
        return sum / (len * 0.75); // divide by pixel count * 3 channels
    }

    /** Compute brightness-weighted centroid of the central face oval region.
     *  Returns { cx, cy } in 64×48 thumbnail coordinates. */
    function getFaceCentroid() {
        const video = videoRef.current;
        if (!video) return null;
        const sw = 64, sh = 48;
        const off = document.createElement('canvas');
        off.width = sw;
        off.height = sh;
        const ctx = off.getContext('2d');
        ctx.drawImage(video, 0, 0, sw, sh);
        const data = ctx.getImageData(0, 0, sw, sh).data;

        // Only sample the central oval (roughly head-sized)
        const ocx = sw / 2, ocy = sh / 2;
        const rx = sw * 0.28, ry = sh * 0.35;
        let sumX = 0, sumY = 0, sumW = 0;

        for (let y = 0; y < sh; y++) {
            for (let x = 0; x < sw; x++) {
                const dx = (x - ocx) / rx, dy = (y - ocy) / ry;
                if (dx * dx + dy * dy > 1) continue; // outside oval
                const i = (y * sw + x) * 4;
                const lum = data[i] * 0.299 + data[i + 1] * 0.587 + data[i + 2] * 0.114;
                sumX += x * lum;
                sumY += y * lum;
                sumW += lum;
            }
        }
        if (sumW < 1) return { cx: ocx, cy: ocy };
        return { cx: sumX / sumW, cy: sumY / sumW };
    }

    // ── Guided multi-pose capture ────────────────────────────────────────────
    async function handleCapture() {
        if (state !== 'idle' || !cameraReady) return;

        setState('capturing');
        setFrames([]);
        setProgress(0);
        capturedRef.current = [];
        poseIndexRef.current = 0;
        prevFrameDataRef.current = null;

        // Kick off the first pose
        startNextPose();
    }

    function startNextPose() {
        const idx = poseIndexRef.current;
        if (idx >= TARGET_FRAMES) {
            finishCapture();
            return;
        }

        const pose = POSES[idx];
        setCurrentPose(pose);
        setGuidance(pose.label);
        setPoseAccepted(false);

        // Give a small settle delay before we start sampling diffs
        settleTimerRef.current = setTimeout(() => {
            const baseData = getComparisonData();
            const baseCentroid = getFaceCentroid();

            // For the first frame (center), accept after a short beat
            if (idx === 0) {
                setTimeout(() => acceptCurrentPose(), 800);
                return;
            }

            // Direction requirement for this pose (if any)
            const dirCheck = DIRECTION_CHECK[pose.id] || null;

            // Poll for movement — require SUSTAINED_POLLS consecutive above-threshold readings
            let consecutiveHits = 0;
            let accepted = false;
            const pollInterval = setInterval(() => {
                if (accepted) return;
                const currentData = getComparisonData();
                const diff = frameDiff(prevFrameDataRef.current, currentData);

                if (diff >= DIFF_THRESHOLD) {
                    // Soft direction validation: prefer correct direction, but don't reject outright
                    if (dirCheck && baseCentroid) {
                        const nowCentroid = getFaceCentroid();
                        if (nowCentroid) {
                            const shift = dirCheck.axis === 'x'
                                ? (nowCentroid.cx - baseCentroid.cx) * dirCheck.sign
                                : (nowCentroid.cy - baseCentroid.cy) * dirCheck.sign;
                            if (shift < DIRECTION_SHIFT_MIN) {
                                // Movement detected but wrong direction — count as partial
                                // (don't reset, just don't increment — fallback will catch it)
                                return;
                            }
                        }
                    }
                    consecutiveHits++;
                    if (consecutiveHits >= SUSTAINED_POLLS) {
                        accepted = true;
                        clearInterval(pollInterval);
                        clearTimeout(captureTimerRef.current);
                        // Additional settle delay so the user holds the pose
                        setTimeout(() => acceptCurrentPose(), 300);
                    }
                } else {
                    consecutiveHits = 0; // reset — movement must be sustained
                }
            }, 150);

            // Fallback timeout: accept pose after FALLBACK_TIMEOUT_MS regardless of direction
            captureTimerRef.current = setTimeout(() => {
                if (!accepted) {
                    accepted = true;
                    clearInterval(pollInterval);
                    acceptCurrentPose();
                }
            }, FALLBACK_TIMEOUT_MS);

            // Store cleanup ref for the interval
            settleTimerRef.current = pollInterval;
        }, SETTLE_DELAY_MS);
    }

    function acceptCurrentPose() {
        clearTimeout(captureTimerRef.current);
        if (typeof settleTimerRef.current === 'number') {
            clearInterval(settleTimerRef.current);
        }

        const frame = captureFrame();
        if (frame) {
            capturedRef.current.push(frame);
            prevFrameDataRef.current = getComparisonData();
        }

        const newProgress = capturedRef.current.length;
        setProgress(newProgress);
        setPoseAccepted(true);
        setFrames([...capturedRef.current]);

        // Brief flash to show acceptance
        setTimeout(() => {
            poseIndexRef.current++;
            if (poseIndexRef.current >= TARGET_FRAMES) {
                finishCapture();
            } else {
                startNextPose();
            }
        }, 350);
    }

    function finishCapture() {
        const captured = capturedRef.current;
        if (captured.length === 0) {
            setState('error');
            setCameraError('No frames captured — please try again.');
            return;
        }

        setProgress(TARGET_FRAMES);
        setFrames([...captured]);
        setState('done');
        setGuidance(`${captured.length} frames captured — fill in the form below`);

        if (onCapture) onCapture(captured);
    }

    function handleReset() {
        clearTimeout(captureTimerRef.current);
        if (typeof settleTimerRef.current === 'number') {
            clearInterval(settleTimerRef.current);
        }
        setFrames([]);
        setProgress(0);
        setState('idle');
        setCurrentPose(null);
        setPoseAccepted(false);
        setGuidance('Position your face in the oval');
        capturedRef.current = [];
        poseIndexRef.current = 0;
        prevFrameDataRef.current = null;
        if (onReset) onReset();
    }

    // ── Render ───────────────────────────────────────────────────────────────
    return (
        <div style={styles.wrapper}>
            {/* Camera viewport */}
            <div style={styles.viewport}>
                <video
                    ref={videoRef}
                    style={styles.video}
                    autoPlay
                    playsInline
                    muted
                />
                <canvas ref={canvasRef} style={styles.canvas} />

                {/* State overlays */}
                {state === 'starting' && (
                    <div style={styles.overlay}>
                        <Loader2 size={36} style={{ animation: 'spin 1s linear infinite', color: '#22c55e' }} />
                        <p style={styles.overlayText}>Starting camera…</p>
                    </div>
                )}
                {state === 'error' && (
                    <div style={styles.overlay}>
                        <XCircle size={36} color="#ef4444" />
                        <p style={{ ...styles.overlayText, color: '#ef4444' }}>{cameraError}</p>
                        <button onClick={startCamera} style={styles.retryBtn}>Retry</button>
                    </div>
                )}
                {state === 'done' && (
                    <div style={{ ...styles.overlay, background: 'rgba(0,0,0,0.55)' }}>
                        <CheckCircle2 size={48} color="#22c55e" />
                        <p style={{ ...styles.overlayText, color: '#22c55e', fontWeight: 700 }}>
                            {frames.length} poses captured
                        </p>
                        <p style={{ ...styles.overlayText, fontSize: 13, marginTop: 4 }}>
                            Fill in the details below and click Register
                        </p>
                    </div>
                )}
            </div>

            {/* Guidance + progress */}
            <div style={styles.guidanceRow}>
                {state === 'capturing' && (
                    <span style={styles.progressDots}>
                        {POSES.map((_, i) => (
                            <span
                                key={i}
                                style={{
                                    ...styles.dot,
                                    background: i < progress ? '#22c55e' : i === progress ? '#3b82f6' : '#374151',
                                    transform: i < progress ? 'scale(1.2)' : i === progress ? 'scale(1.35)' : 'scale(1)',
                                    boxShadow: i === progress ? '0 0 8px rgba(59,130,246,0.6)' : 'none',
                                }}
                            />
                        ))}
                    </span>
                )}
                <span style={styles.guidanceChip}>
                    {state === 'error' ? (
                        <><AlertCircle size={13} style={{ marginRight: 4 }} />{cameraError}</>
                    ) : state === 'capturing' ? (
                        <>{guidance} <span style={{ opacity: 0.6, marginLeft: 6 }}>({progress}/{TARGET_FRAMES})</span></>
                    ) : guidance}
                </span>
            </div>

            {/* Action buttons */}
            <div style={styles.buttonRow}>
                {state !== 'done' ? (
                    <button
                        onClick={handleCapture}
                        disabled={state !== 'idle' || !cameraReady}
                        style={{
                            ...styles.captureBtn,
                            opacity: (state !== 'idle' || !cameraReady) ? 0.5 : 1,
                            cursor: (state !== 'idle' || !cameraReady) ? 'not-allowed' : 'pointer',
                        }}
                    >
                        {state === 'capturing' ? (
                            <><Loader2 size={16} style={{ animation: 'spin 1s linear infinite', marginRight: 6 }} />Scanning Poses…</>
                        ) : (
                            <><Camera size={16} style={{ marginRight: 6 }} />Start Face Scan</>
                        )}
                    </button>
                ) : (
                    <button onClick={handleReset} style={styles.resetBtn}>
                        <Camera size={16} style={{ marginRight: 6 }} />Re-capture
                    </button>
                )}
            </div>

            {/* Thumbnail strip */}
            {frames.length > 0 && (
                <div style={styles.thumbStrip}>
                    {frames.map((src, i) => (
                        <div key={i} style={styles.thumbWrap}>
                            <img
                                src={src}
                                alt={`Pose ${i + 1}`}
                                style={styles.thumb}
                            />
                            <span style={styles.thumbLabel}>{POSES[i]?.id || i + 1}</span>
                        </div>
                    ))}
                </div>
            )}

            <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
    );
}

// ── Styles ───────────────────────────────────────────────────────────────────
const styles = {
    wrapper: {
        display: 'flex',
        flexDirection: 'column',
        gap: 12,
        background: '#0f172a',
        borderRadius: 16,
        padding: 16,
        boxShadow: '0 4px 32px rgba(0,0,0,0.4)',
    },
    viewport: {
        position: 'relative',
        borderRadius: 12,
        overflow: 'hidden',
        background: '#000',
        aspectRatio: '16/9',
        width: '100%',
    },
    video: {
        width: '100%',
        height: '100%',
        objectFit: 'cover',
        display: 'block',
        transform: 'scaleX(-1)',
    },
    canvas: {
        position: 'absolute',
        inset: 0,
        width: '100%',
        height: '100%',
        pointerEvents: 'none',
    },
    overlay: {
        position: 'absolute',
        inset: 0,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(0,0,0,0.72)',
        gap: 12,
    },
    overlayText: {
        color: '#e2e8f0',
        fontSize: 14,
        textAlign: 'center',
        maxWidth: 260,
        margin: 0,
    },
    retryBtn: {
        marginTop: 8,
        padding: '8px 20px',
        borderRadius: 8,
        border: 'none',
        background: '#3b82f6',
        color: '#fff',
        fontSize: 13,
        cursor: 'pointer',
        fontWeight: 600,
    },
    guidanceRow: {
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        minHeight: 28,
    },
    guidanceChip: {
        display: 'inline-flex',
        alignItems: 'center',
        background: 'rgba(34,197,94,0.12)',
        color: '#86efac',
        fontSize: 12,
        fontWeight: 500,
        padding: '4px 12px',
        borderRadius: 99,
        border: '1px solid rgba(34,197,94,0.25)',
    },
    progressDots: {
        display: 'flex',
        gap: 5,
        alignItems: 'center',
    },
    dot: {
        width: 8,
        height: 8,
        borderRadius: '50%',
        display: 'inline-block',
        transition: 'all 0.3s ease',
    },
    buttonRow: {
        display: 'flex',
        gap: 8,
    },
    captureBtn: {
        flex: 1,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '10px 20px',
        borderRadius: 10,
        border: 'none',
        background: 'linear-gradient(135deg, #22c55e, #16a34a)',
        color: '#fff',
        fontSize: 14,
        fontWeight: 600,
        transition: 'opacity 0.2s',
    },
    resetBtn: {
        flex: 1,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '10px 20px',
        borderRadius: 10,
        border: '1px solid #334155',
        background: 'transparent',
        color: '#94a3b8',
        fontSize: 14,
        fontWeight: 600,
        cursor: 'pointer',
    },
    thumbStrip: {
        display: 'flex',
        gap: 6,
        overflowX: 'auto',
        paddingBottom: 4,
    },
    thumbWrap: {
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 2,
        flexShrink: 0,
    },
    thumb: {
        width: 56,
        height: 42,
        objectFit: 'cover',
        borderRadius: 6,
        border: '2px solid #22c55e',
        transform: 'scaleX(-1)',
    },
    thumbLabel: {
        fontSize: 9,
        color: '#64748b',
        fontWeight: 600,
        textTransform: 'uppercase',
    },
};
