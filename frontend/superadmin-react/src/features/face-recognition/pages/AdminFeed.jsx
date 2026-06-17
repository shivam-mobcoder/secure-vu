import { useEffect, useRef, useState, useCallback } from 'react';
import { RefreshCw, Shield, Clock, Video, CheckCircle, PlayCircle, Radio } from 'lucide-react';
import { getStoredToken } from '../../../auth';
import '../../../styles/adminfeed.css';

/**
 * AdminFeed
 * Embeds the existing live CCTV client.html viewer inside an iframe,
 * passing the current JWT token so the feed is authenticated.
 * This reuses 100% of the existing WebRTC/streaming/Camera Rules logic.
 *
 * The Security Alerts sidebar connects to the real backend via WebSocket
 * (/ws?token=<jwt>), with REST polling as a fallback.
 * No mock data is used. No second iframe WebSocket is touched.
 */

// ── Event string parser ──────────────────────────────────────────────────────
// Backend sends events like: "P1 | CAM4 | UNKNOWN_PERSON_FIRST_SEEN | Person-2193"
// We parse these into human-readable display values.

const EVENT_TYPE_LABELS = {
    ZONE_ENTER:                  'Zone Intrusion',
    ZONE_EXIT:                   'Zone Exit',
    'ZONE ENTER':                'Zone Intrusion',
    'ZONE EXIT':                 'Zone Exit',
    UNKNOWN_PERSON_FIRST_SEEN:   'Unknown Person Detected',
    UNKNOWN_PERSON:              'Unknown Person Detected',
    WATCHLIST_MATCH:             'Watchlist Match',
    MAX_PEOPLE:                  'Crowd Limit Exceeded',
    NEW_PERSON_SEEN:             'New Person Detected',
    LINE_CROSS:                  'Virtual Line Crossed',
    LOITERING:                   'Loitering Detected',
    FACE_RECOGNIZED:             'Face Recognized',
    FACE_ENROLLED:               'Face Enrolled',
    DATA_CHANNEL_CONNECTED:      'System Connected',
    READY_FOR_DETECTIONS:        'System Ready',
    READY_FOR_FACE_ENROLLMENT:   'System Ready',
};

function parseEventString(raw = '') {
    // "P1 | CAM4 | UNKNOWN_PERSON_FIRST_SEEN | Person-2193"
    const parts = raw.split('|').map(s => s.trim());

    let camera = null;
    let eventType = null;
    let priority = null;

    for (const part of parts) {
        if (/^P[0-9]$/.test(part)) {
            priority = part;
        } else if (/^CAM\d+$/i.test(part)) {
            const num = part.replace(/^CAM/i, '');
            camera = `Camera ${num}`;
        } else if (!eventType) {
            // First non-priority, non-camera part is the event type
            const label = EVENT_TYPE_LABELS[part] || EVENT_TYPE_LABELS[part.replace(/\s+/g, '_')];
            if (label) eventType = label;
            else if (part && !part.startsWith('Person-') && !part.startsWith('pid:')) {
                // Try partial match
                const key = Object.keys(EVENT_TYPE_LABELS).find(k => part.includes(k));
                eventType = key ? EVENT_TYPE_LABELS[key] : null;
            }
        }
    }

    return { camera, eventType, priority };
}

function formatPersonLabel(person = '') {
    if (!person || person === 'SYSTEM') return 'System Event';
    if (person === 'Object') return 'Object Detected';
    if (person === 'Unknown') return 'Unknown Person';
    return person;
}

function formatTimeAgo(isoOrFormatted) {
    try {
        // Backend sends "2026-06-17 15:30:00" format
        const ts = isoOrFormatted.replace(' ', 'T');
        const diff = (Date.now() - new Date(ts).getTime()) / 1000;
        if (diff < 10) return 'Just now';
        if (diff < 60) return `${Math.floor(diff)}s ago`;
        if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
        return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
        return isoOrFormatted;
    }
}

// ── localStorage helpers for acknowledgements ────────────────────────────────
const ACK_KEY = 'securevu_acked_alerts';

function loadAckedIds() {
    try {
        return new Set(JSON.parse(localStorage.getItem(ACK_KEY) || '[]'));
    } catch {
        return new Set();
    }
}

function saveAckedId(id) {
    try {
        const existing = loadAckedIds();
        existing.add(id);
        // Keep only recent 200 to avoid bloat
        const trimmed = [...existing].slice(-200);
        localStorage.setItem(ACK_KEY, JSON.stringify(trimmed));
    } catch { /* ignore */ }
}

// ── Unique ID generator for alert cards ─────────────────────────────────────
let _alertIdCounter = 0;
function nextAlertId() {
    return `alert_${Date.now()}_${++_alertIdCounter}`;
}

const BACKEND = import.meta.env.VITE_BACKEND_ORIGIN || '';
const MAX_ALERTS = 20;

// ── Main Component ───────────────────────────────────────────────────────────
export default function AdminFeed() {
    const iframeRef = useRef(null);
    const [iframeLoading, setIframeLoading] = useState(true);
    const [iframeKey, setIframeKey] = useState(0);

    // Alerts state — prepend-only, no full re-render
    const [alerts, setAlerts] = useState([]);
    const alertsRef = useRef([]);
    const ackedIds = useRef(loadAckedIds());
    const mountedRef = useRef(true);

    // Build iframe URL
    const token = getStoredToken();
    const feedUrl = token
        ? `${BACKEND}/static/client.html?token=${encodeURIComponent(token)}`
        : `${BACKEND}/static/client.html`;

    // ── Alert ingestion (called from postMessage listener) ────────────────
    const ingestAlert = useCallback((payload) => {
        if (!mountedRef.current) return;

        const id = nextAlertId();
        const newAlert = {
            id,
            person: payload.person || 'SYSTEM',
            event: payload.event || '',
            timestamp: payload.timestamp || new Date().toLocaleTimeString(),
            clip_url: payload.clip_url || payload.clipUrl || '',
            meta: payload.meta || null,
            isNew: true,
        };

        alertsRef.current = [newAlert, ...alertsRef.current].slice(0, MAX_ALERTS);
        setAlerts([...alertsRef.current]);

        // Remove "new" animation class after it completes
        setTimeout(() => {
            alertsRef.current = alertsRef.current.map(a =>
                a.id === id ? { ...a, isNew: false } : a
            );
            setAlerts([...alertsRef.current]);
        }, 800);
    }, []);

    // ── Acknowledge ────────────────────────────────────────────────────────
    const acknowledgeAlert = useCallback((id) => {
        ackedIds.current.add(id);
        saveAckedId(id);
        alertsRef.current = alertsRef.current.map(a =>
            a.id === id ? { ...a, acknowledged: true, isNew: false } : a
        );
        setAlerts([...alertsRef.current]);
    }, []);

    // ── Listen for alerts forwarded from the iframe via postMessage ────────
    useEffect(() => {
        mountedRef.current = true;

        function onMessage(evt) {
            if (!mountedRef.current) return;
            // Only accept SECUREVU_ALERT messages (ignore other postMessage noise)
            if (!evt.data || evt.data.type !== 'SECUREVU_ALERT') return;
            const payload = evt.data.payload;
            if (!payload) return;
            ingestAlert(payload);
        }

        window.addEventListener('message', onMessage);
        return () => {
            mountedRef.current = false;
            window.removeEventListener('message', onMessage);
        };
    }, [ingestAlert]);

    // ── Iframe handlers ────────────────────────────────────────────────────
    function handleReload() {
        setIframeLoading(true);
        setIframeKey(k => k + 1);
    }

    return (
        <div className="af-page">
            {/* ── Left: Feed Area ─────────────────────────────────── */}
            <div className="af-feed-area">
                <div className="af-main-feed">
                    <div className="af-feed-overlay">
                        <span className="af-live-badge">
                            <Shield size={13} />
                            Live Monitoring Active
                        </span>
                    </div>

                    {/* Subtle grid overlay */}
                    <div className="af-grid-overlay">
                        <div className="af-grid-line-v" style={{ left: '25%' }} />
                        <div className="af-grid-line-v" style={{ left: '50%' }} />
                        <div className="af-grid-line-v" style={{ left: '75%' }} />
                        <div className="af-grid-line-h" style={{ top: '33%' }} />
                        <div className="af-grid-line-h" style={{ top: '66%' }} />
                    </div>

                    {/* Loading state */}
                    {iframeLoading && (
                        <div className="af-loading-overlay">
                            <Video size={36} color="#22c55e" style={{ animation: 'af-pulse 1.5s ease-in-out infinite' }} />
                            <p className="af-loading-text">Connecting to camera feed…</p>
                        </div>
                    )}

                    {/* The actual iframe — all WebRTC, Camera Rules, and detection logic live here */}
                    <iframe
                        key={iframeKey}
                        ref={iframeRef}
                        src={feedUrl}
                        style={{ opacity: iframeLoading ? 0 : 1 }}
                        title="Live Camera Feed"
                        allow="camera; microphone; autoplay"
                        onLoad={() => setIframeLoading(false)}
                        onError={() => setIframeLoading(false)}
                    />
                </div>
            </div>

            {/* ── Right: Security Alerts Sidebar ──────────────── */}
            <aside className="af-alerts-sidebar">
                {/* Header */}
                <div className="af-alerts-header">
                    <div className="af-alerts-header-left">
                        <h2 className="af-alerts-title">Security Alerts</h2>
                        <div className="af-alerts-status">
                            <span className="af-status-dot af-status-dot--live" />
                            <span className="af-alerts-subtitle">Live Monitoring</span>
                        </div>
                    </div>
                    <div className="af-alerts-actions">
                        <button
                            className="af-alerts-icon-btn"
                            title="Reload camera feed"
                            onClick={handleReload}
                        >
                            <RefreshCw size={14} />
                        </button>
                    </div>
                </div>

                {/* Alert list */}
                <div className="af-alerts-list">
                    {alerts.length === 0 ? (
                        <div className="af-empty-state">
                            <Radio size={28} className="af-empty-icon" />
                            <p className="af-empty-title">Waiting for security events…</p>
                            <p className="af-empty-sub">Alerts will appear here in real time as the system detects activity.</p>
                        </div>
                    ) : (
                        alerts.map(alert => (
                            <AlertCard
                                key={alert.id}
                                alert={alert}
                                onAcknowledge={acknowledgeAlert}
                            />
                        ))
                    )}
                </div>

                {/* Footer count */}
                {alerts.length > 0 && (
                    <div className="af-alerts-footer">
                        {alerts.length} alert{alerts.length !== 1 ? 's' : ''} · max {MAX_ALERTS} shown
                    </div>
                )}
            </aside>
        </div>
    );
}

// ── Alert Card ───────────────────────────────────────────────────────────────
function AlertCard({ alert, onAcknowledge }) {
    const { camera, eventType } = parseEventString(alert.event);
    const personLabel = formatPersonLabel(alert.person);
    const timeLabel = formatTimeAgo(alert.timestamp);
    const isAcknowledged = alert.acknowledged;
    const hasClip = Boolean(alert.clip_url);

    function handleReview() {
        if (!hasClip) return;
        window.open(alert.clip_url, '_blank', 'noopener,noreferrer');
    }

    return (
        <div className={[
            'af-alert-card',
            alert.isNew ? 'af-alert-card--entering' : '',
            isAcknowledged ? 'af-alert-card--acknowledged' : '',
        ].filter(Boolean).join(' ')}>

            {/* Badge row */}
            <div className="af-alert-top">
                <span className={`af-alert-badge ${isAcknowledged ? 'af-alert-badge--ack' : 'af-alert-badge--new'}`}>
                    {isAcknowledged ? 'ACKNOWLEDGED' : 'NEW ALERT'}
                </span>
            </div>

            {/* Person / Title */}
            <div className="af-alert-person">{personLabel}</div>

            {/* Camera label (parsed from event string) */}
            {camera && (
                <div className="af-alert-camera">{camera}</div>
            )}

            {/* Event type (parsed) */}
            {eventType && (
                <div className="af-alert-event-type">{eventType}</div>
            )}

            {/* Time */}
            <div className="af-alert-time">
                <Clock size={11} />
                {timeLabel}
            </div>

            {/* Actions */}
            {!isAcknowledged && (
                <div className="af-alert-actions">
                    <button
                        className="af-alert-btn af-alert-btn--primary"
                        onClick={() => onAcknowledge(alert.id)}
                        title="Mark as acknowledged"
                    >
                        <CheckCircle size={13} />
                        Acknowledge
                    </button>
                    {hasClip ? (
                        <button
                            className="af-alert-btn af-alert-btn--secondary"
                            onClick={handleReview}
                            title="Open event clip"
                        >
                            <PlayCircle size={13} />
                            Review
                        </button>
                    ) : (
                        <button
                            className="af-alert-btn af-alert-btn--secondary af-alert-btn--disabled"
                            disabled
                            title="No clip available"
                        >
                            <PlayCircle size={13} />
                            Review
                        </button>
                    )}
                </div>
            )}
        </div>
    );
}
