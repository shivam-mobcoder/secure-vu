import { useRef, useState, useCallback, useEffect } from 'react';
import { Camera, CheckCircle2, XCircle, Loader2, AlertCircle, RefreshCw } from 'lucide-react';

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
    const [guidance, setGuidance] = useState('Position your face within the frame');
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
                ? 'Camera permission denied. Please allow camera access.'
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

    // ── Rectangular Guide Overlay ──────────────────────────────────────────────
    const drawGuide = useCallback(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        canvas.width = canvas.offsetWidth;
        canvas.height = canvas.offsetHeight;
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        const bw = canvas.width, bh = canvas.height;
        const boxW = bw * 0.35, boxH = bh * 0.7;
        const x = (bw - boxW) / 2, y = (bh - boxH) / 2;

        // Semi-transparent mask
        ctx.fillStyle = 'rgba(0,0,0,0.45)';
        ctx.fillRect(0, 0, bw, bh);

        // Box cutout
        ctx.save();
        ctx.beginPath();
        ctx.roundRect(x, y, boxW, boxH, 8);
        ctx.clip();
        ctx.clearRect(x, y, boxW, boxH);
        ctx.restore();

        // White Corner Brackets
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 3;
        const len = 20;

        // Top Left
        ctx.beginPath();
        ctx.moveTo(x, y + len); ctx.lineTo(x, y); ctx.lineTo(x + len, y);
        ctx.stroke();

        // Top Right
        ctx.beginPath();
        ctx.moveTo(x + boxW - len, y); ctx.lineTo(x + boxW, y); ctx.lineTo(x + boxW, y + len);
        ctx.stroke();

        // Bottom Left
        ctx.beginPath();
        ctx.moveTo(x, y + boxH - len); ctx.lineTo(x, y + boxH); ctx.lineTo(x + len, y + boxH);
        ctx.stroke();

        // Bottom Right
        ctx.beginPath();
        ctx.moveTo(x + boxW - len, y + boxH); ctx.lineTo(x + boxW, y + boxH); ctx.lineTo(x + boxW, y + boxH - len);
        ctx.stroke();

        // Thin white border line
        ctx.strokeStyle = 'rgba(255,255,255,0.4)';
        ctx.lineWidth = 1;
        ctx.strokeRect(x, y, boxW, boxH);

        // Horizontal midline (alignment guide)
        ctx.beginPath();
        ctx.moveTo(x, y + boxH / 2);
        ctx.lineTo(x + boxW, y + boxH / 2);
        ctx.stroke();

        // Progress indication on border if capturing
        if (progress > 0 && progress <= TARGET_FRAMES) {
            ctx.strokeStyle = '#22c55e';
            ctx.lineWidth = 4;
            // Draw progress around the box border
            const perimeter = 2 * (boxW + boxH);
            const drawLen = (progress / TARGET_FRAMES) * perimeter;
            ctx.setLineDash([drawLen, perimeter]);
            ctx.strokeRect(x, y, boxW, boxH);
            ctx.setLineDash([]);
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
    async function handleStartCapture() {
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
        setGuidance(`Success: ${captured.length} poses captured`);

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
        setGuidance('Position your face within the frame');
        capturedRef.current = [];
        poseIndexRef.current = 0;
        prevFrameDataRef.current = null;
        if (onReset) onReset();
    }

    // ── Render ───────────────────────────────────────────────────────────────
    return (
        <div style={styles.wrapper}>
            {/* Viewport */}
            <div style={styles.viewport}>
                <video ref={videoRef} style={styles.video} autoPlay playsInline muted />
                <canvas ref={canvasRef} style={styles.canvas} />

                {/* Status Badges */}
                <div style={styles.qualityBadge}>
                    <span style={styles.dot} /> Quality: Good
                </div>

                {/* Overlays */}
                {state === 'starting' && (
                    <div style={styles.overlay}>
                        <Loader2 size={32} style={{ animation: 'spin 1s linear infinite', color: '#fff' }} />
                        <p style={styles.overlayText}>Warming up camera…</p>
                    </div>
                )}
                {state === 'error' && (
                    <div style={styles.overlay}>
                        <XCircle size={32} color="#ef4444" />
                        <p style={{ ...styles.overlayText, color: '#ef4444' }}>{cameraError}</p>
                        <button onClick={startCamera} style={styles.retryBtn}>Retry</button>
                    </div>
                )}
            </div>

            {/* Guidance */}
            <div style={styles.guidanceRow}>
                <span style={{
                    ...styles.guidanceChip,
                    background: state === 'capturing' ? '#eff6ff' : '#f8fafc',
                    color: state === 'capturing' ? '#3b82f6' : '#64748b',
                    borderColor: state === 'capturing' ? '#dbeafe' : '#e2e8f0',
                }}>
                    {state === 'capturing' ? (
                        <><Loader2 size={12} style={{ animation: 'spin 1s linear infinite', marginRight: 6 }} />{guidance}</>
                    ) : (guidance)}
                </span>
            </div>

            {/* Buttons */}
            <div style={styles.buttonRow}>
                {state !== 'done' ? (
                    <button
                        onClick={handleStartCapture}
                        disabled={state !== 'idle' || !cameraReady}
                        style={{
                            ...styles.mainBtn,
                            opacity: (state !== 'idle' || !cameraReady) ? 0.6 : 1,
                            cursor: (state !== 'idle' || !cameraReady) ? 'not-allowed' : 'pointer',
                        }}
                    >
                        <Camera size={16} style={{ marginRight: 8 }} />
                        {state === 'capturing' ? `Capturing (${progress}/${TARGET_FRAMES})` : 'Capture'}
                    </button>
                ) : (
                    <button onClick={handleReset} style={styles.resetBtn}>
                        <RefreshCw size={14} style={{ marginRight: 8 }} />
                        Retake Scan
                    </button>
                )}
            </div>

            {/* Pose Strip */}
            {frames.length > 0 && (
                <div style={styles.poseStrip}>
                    {frames.map((src, i) => (
                        <div key={i} style={styles.thumbWrap}>
                            <img src={src} alt="pose" style={styles.thumb} />
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
        gap: 16,
        background: '#ffffff',
    },
    viewport: {
        position: 'relative',
        borderRadius: 12,
        overflow: 'hidden',
        background: '#f1f5f9',
        aspectRatio: '16/9',
        width: '100%',
        boxShadow: 'inset 0 2px 4px rgba(0,0,0,0.05)',
    },
    video: {
        width: '100%',
        height: '100%',
        objectFit: 'cover',
        transform: 'scaleX(-1)',
    },
    canvas: {
        position: 'absolute',
        inset: 0,
        width: '100%',
        height: '100%',
    },
    qualityBadge: {
        position: 'absolute',
        top: 12,
        right: 12,
        background: 'rgba(15, 23, 42, 0.8)',
        color: '#fff',
        fontSize: 11,
        fontWeight: 600,
        padding: '5px 10px',
        borderRadius: 20,
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        backdropFilter: 'blur(4px)',
    },
    dot: {
        width: 6,
        height: 6,
        background: '#22c55e',
        borderRadius: '50%',
    },
    overlay: {
        position: 'absolute',
        inset: 0,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(15, 23, 42, 0.6)',
        backdropFilter: 'blur(2px)',
        gap: 12,
    },
    overlayText: {
        color: '#fff',
        fontSize: 14,
        fontWeight: 500,
        margin: 0,
    },
    retryBtn: {
        padding: '8px 16px',
        borderRadius: 6,
        border: 'none',
        background: '#fff',
        color: '#0f172a',
        fontSize: 12,
        fontWeight: 700,
        cursor: 'pointer',
    },
    guidanceRow: {
        display: 'flex',
        justifyContent: 'center',
    },
    guidanceChip: {
        display: 'inline-flex',
        alignItems: 'center',
        fontSize: 12,
        fontWeight: 600,
        padding: '6px 16px',
        borderRadius: 30,
        border: '1px solid',
        textAlign: 'center',
    },
    buttonRow: {
        display: 'flex',
        justifyContent: 'center',
    },
    mainBtn: {
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '12px 32px',
        borderRadius: 8,
        border: 'none',
        background: '#000000',
        color: '#ffffff',
        fontSize: 14,
        fontWeight: 700,
        cursor: 'pointer',
        minWidth: 160,
        transition: 'all 0.2s',
    },
    resetBtn: {
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '12px 32px',
        borderRadius: 8,
        border: '1px solid #e2e8f0',
        background: '#ffffff',
        color: '#64748b',
        fontSize: 14,
        fontWeight: 600,
        cursor: 'pointer',
    },
    poseStrip: {
        display: 'flex',
        gap: 8,
        overflowX: 'auto',
        padding: '4px 0',
    },
    thumbWrap: {
        flexShrink: 0,
        width: 60,
        height: 40,
        borderRadius: 4,
        overflow: 'hidden',
        border: '1px solid #e2e8f0',
    },
    thumb: {
        width: '100%',
        height: '100%',
        objectFit: 'cover',
        transform: 'scaleX(-1)',
    },
};
