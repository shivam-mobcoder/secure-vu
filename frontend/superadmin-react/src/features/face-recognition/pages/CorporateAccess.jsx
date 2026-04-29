import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
    ArrowLeft,
    ScanFace,
    Shield,
    CheckCircle2,
    Building2,
    Hash,
    CalendarDays,
    BadgeCheck,
    Video,
} from 'lucide-react';
import '../../../styles/corporate-access.css';

/* ── Mock employee data (simulated detection result) ── */
const MOCK_PERSON = {
    name: 'Eleanor Rigby',
    title: 'Senior Systems Architect',
    initials: 'E',
    employeeId: 'EMP-004251',
    department: 'Engineering',
    status: 'Active',
    lastAccess: 'Today, 08:15 AM',
};

const RECENT_LOG = [
    { initials: 'MK', name: 'Michael Keane', role: 'DevOps Lead', time: '08:12 AM' },
    { initials: 'SL', name: 'Sarah Livingston', role: 'QA Manager', time: '08:09 AM' },
    { initials: 'JP', name: 'James Parker', role: 'Software Engineer', time: '08:03 AM' },
];

export default function CorporateAccess() {
    const videoRef = useRef(null);
    const [cameraReady, setCameraReady] = useState(false);
    const [cameraError, setCameraError] = useState(false);
    const [detected, setDetected] = useState(false);
    const [latency, setLatency] = useState(42);

    /* ── Start webcam ──────────────────────────────── */
    useEffect(() => {
        let stream = null;

        async function startCamera() {
            try {
                // navigator.mediaDevices is undefined on insecure (non-HTTPS) origins
                if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                    console.warn('Camera API unavailable — page must be served over HTTPS or localhost.');
                    setCameraError(true);
                    return;
                }

                stream = await navigator.mediaDevices.getUserMedia({
                    video: { width: 1280, height: 720, facingMode: 'user' },
                    audio: false,
                });
                if (videoRef.current) {
                    videoRef.current.srcObject = stream;
                    setCameraReady(true);
                }
            } catch (err) {
                console.warn('Camera error:', err.message);
                setCameraError(true);
            }
        }

        startCamera();

        return () => {
            if (stream) stream.getTracks().forEach((t) => t.stop());
        };
    }, []);

    /* ── Simulated face detection (demo) ───────────── */
    /* Triggers after 3.5s whether the camera is live or offline */
    useEffect(() => {
        const timer = setTimeout(() => setDetected(true), 3500);
        return () => clearTimeout(timer);
    }, []);

    /* ── Simulated latency fluctuation ─────────────── */
    useEffect(() => {
        const id = setInterval(() => {
            setLatency(Math.floor(35 + Math.random() * 20));
        }, 2000);
        return () => clearInterval(id);
    }, []);

    return (
        <div className="ca-page">
            {/* ── Top Bar ──────────────────────────── */}
            <div className="ca-topbar">
                <div className="ca-topbar-left">
                    <h1>Corporate Access Control</h1>
                    <p className="ca-topbar-breadcrumb">
                        Building A<span>•</span>Main Lobby<span>•</span>Terminal 04
                    </p>
                </div>
                <Link to="/admin/dashboard/live-feed" className="ca-back-link">
                    <ArrowLeft size={15} />
                    Back to Live Feed
                </Link>
            </div>

            {/* ── Content ─────────────────────────── */}
            <div className="ca-content">
                {/* Left: Camera */}
                <div className="ca-camera-wrap">
                    <div className="ca-camera-container">
                        {cameraError ? (
                            <div className="ca-camera-placeholder">
                                <Video size={36} color="#475569" />
                                <p>Camera unavailable</p>
                            </div>
                        ) : (
                            <>
                                <video
                                    ref={videoRef}
                                    className="ca-camera-video"
                                    autoPlay
                                    playsInline
                                    muted
                                />

                                {/* Quality badge */}
                                <div className="ca-quality-badge">
                                    <span className="ca-quality-dot" />
                                    Quality: Good
                                </div>

                                {/* Scanning overlay */}
                                <div className="ca-scan-overlay">
                                    <div className={`ca-scan-box ${detected ? 'ca-scan-box--detected' : ''}`}>
                                        <div className="ca-scan-corner ca-scan-corner--tl" />
                                        <div className="ca-scan-corner ca-scan-corner--tr" />
                                        <div className="ca-scan-corner ca-scan-corner--bl" />
                                        <div className="ca-scan-corner ca-scan-corner--br" />
                                        {!detected && <div className="ca-scan-line" />}
                                    </div>
                                </div>
                            </>
                        )}
                    </div>

                    {/* Status Bar */}
                    <div className="ca-status-bar">
                        <div className="ca-status-indicator">
                            <span className={`ca-status-dot ${cameraError ? 'ca-status-dot--error' : ''}`} />
                            {cameraError ? 'Camera Offline' : 'System Ready'}
                        </div>
                        <span className="ca-status-latency">LATENCY: {latency}ms</span>
                    </div>
                </div>

                {/* Right: Person Card */}
                <div className="ca-person-panel">
                    <div className="ca-person-card">
                        {detected ? (
                            <div className="ca-animate-in">
                                {/* Access badge */}
                                <div className="ca-access-header">
                                    <span className="ca-access-badge ca-access-badge--granted">
                                        <CheckCircle2 size={14} />
                                        Access Granted
                                    </span>
                                </div>

                                {/* Person info */}
                                <div className="ca-person-info">
                                    <div className="ca-person-avatar">
                                        {MOCK_PERSON.initials}
                                    </div>
                                    <h2 className="ca-person-name">{MOCK_PERSON.name}</h2>
                                    <p className="ca-person-title">{MOCK_PERSON.title}</p>
                                </div>

                                {/* Metadata */}
                                <div className="ca-person-meta">
                                    <div className="ca-meta-item">
                                        <span className="ca-meta-label">Employee ID</span>
                                        <span className="ca-meta-value">
                                            <Hash size={14} />
                                            {MOCK_PERSON.employeeId}
                                        </span>
                                    </div>
                                    <div className="ca-meta-item">
                                        <span className="ca-meta-label">Department</span>
                                        <span className="ca-meta-value">
                                            <Building2 size={14} />
                                            {MOCK_PERSON.department}
                                        </span>
                                    </div>
                                    <div className="ca-meta-item">
                                        <span className="ca-meta-label">Status</span>
                                        <span className="ca-meta-value">
                                            <BadgeCheck size={14} />
                                            {MOCK_PERSON.status}
                                        </span>
                                    </div>
                                    <div className="ca-meta-item">
                                        <span className="ca-meta-label">Last Access</span>
                                        <span className="ca-meta-value">
                                            <CalendarDays size={14} />
                                            {MOCK_PERSON.lastAccess}
                                        </span>
                                    </div>
                                </div>

                                {/* Recent log */}
                                <div className="ca-recent-log">
                                    <h3 className="ca-recent-log-title">Recent Access</h3>
                                    {RECENT_LOG.map((entry) => (
                                        <div key={entry.name} className="ca-log-entry">
                                            <div className="ca-log-avatar">{entry.initials}</div>
                                            <div className="ca-log-info">
                                                <p className="ca-log-name">{entry.name}</p>
                                                <p className="ca-log-role">{entry.role}</p>
                                            </div>
                                            <span className="ca-log-time">{entry.time}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        ) : (
                            /* Waiting state */
                            <div className="ca-waiting-state">
                                <div className="ca-waiting-icon">
                                    <ScanFace size={30} />
                                </div>
                                <h3 className="ca-waiting-title">Waiting for Detection</h3>
                                <p className="ca-waiting-subtitle">
                                    Position your face within the scanning area.
                                    <br />
                                    The system will identify you automatically.
                                </p>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
