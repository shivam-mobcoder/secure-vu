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
        let ts = isoOrFormatted;
        if (ts.includes(' ') && !ts.includes('T')) {
            ts = ts.replace(' ', 'T');
        }
        const parsed = new Date(ts).getTime();
        if (isNaN(parsed)) {
            return isoOrFormatted;
        }
        const diff = (Date.now() - parsed) / 1000;
        if (diff < 5) return 'just now';
        if (diff < 60) return `${Math.floor(diff)} seconds ago`;
        const mins = Math.floor(diff / 60);
        if (mins < 60) return `${mins} minute${mins !== 1 ? 's' : ''} ago`;
        const hrs = Math.floor(mins / 60);
        if (hrs < 24) return `${hrs} hour${hrs !== 1 ? 's' : ''} ago`;
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

const ENROLLMENT_GUIDANCE_KEYWORDS = [
    'good face captured',
    'move closer',
    'move slightly back',
    'hold still',
    'turn head',
    'move face into frame',
    'move your face into frame',
    'ready for face enrollment',
    'starting face enrollment',
    'database reloaded',
    'enrollment complete',
    'follow instructions',
    'send frames now',
];

function isDisplayableAlert(payload) {
    const event = (payload?.event || '').toString();
    if (!event) return false;
    const normalized = event.toLowerCase();
    return !ENROLLMENT_GUIDANCE_KEYWORDS.some((k) => normalized.includes(k));
}

function alertDedupeKey(payload) {
    return `${payload?.timestamp || ''}|${payload?.person || ''}|${payload?.event || ''}`;
}

function buildAlertWsUrl(token) {
    const origin = BACKEND || window.location.origin;
    const url = new URL('/ws', origin);
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    url.searchParams.set('token', token);
    return url.toString();
}

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
    const seenAlertKeysRef = useRef(new Set());
    const [wsStatus, setWsStatus] = useState('connecting');

    // Build iframe URL
    const token = getStoredToken();
    const feedUrl = token
        ? `${BACKEND}/static/client.html?token=${encodeURIComponent(token)}`
        : `${BACKEND}/static/client.html`;

    // ── Alert ingestion (called from postMessage listener) ────────────────
    const ingestAlert = useCallback((payload) => {
        if (!mountedRef.current || !payload) return;
        if (!isDisplayableAlert(payload)) return;

        const dedupeKey = alertDedupeKey(payload);
        if (seenAlertKeysRef.current.has(dedupeKey)) return;
        seenAlertKeysRef.current.add(dedupeKey);
        if (seenAlertKeysRef.current.size > 500) {
            seenAlertKeysRef.current = new Set([...seenAlertKeysRef.current].slice(-250));
        }

        const id = nextAlertId();
        let ts = payload.timestamp;
        if (!ts || (ts.includes(':') && !ts.includes('-') && !ts.includes('/'))) {
            ts = new Date().toISOString();
        }
        const newAlert = {
            id,
            person: payload.person || 'SYSTEM',
            event: payload.event || '',
            timestamp: ts,
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

    // ── Direct WebSocket to backend (primary alert channel) ───────────────
    useEffect(() => {
        if (!token) {
            setWsStatus('offline');
            return undefined;
        }

        let ws = null;
        let reconnectTimer = null;
        let closed = false;

        function connect() {
            if (closed) return;
            setWsStatus('connecting');
            try {
                ws = new WebSocket(buildAlertWsUrl(token));
            } catch {
                setWsStatus('reconnecting');
                reconnectTimer = setTimeout(connect, 2000);
                return;
            }

            ws.onopen = () => {
                if (!closed) setWsStatus('connected');
            };

            ws.onmessage = (evt) => {
                try {
                    const data = JSON.parse(evt.data);
                    if (data && data.event && data.person && !data.action) {
                        ingestAlert(data);
                    }
                } catch {
                    // ignore non-JSON frames
                }
            };

            ws.onclose = () => {
                if (closed) return;
                setWsStatus('reconnecting');
                reconnectTimer = setTimeout(connect, 2000);
            };

            ws.onerror = () => {
                try { ws?.close(); } catch { /* ignore */ }
            };
        }

        connect();

        return () => {
            closed = true;
            if (reconnectTimer) clearTimeout(reconnectTimer);
            try { ws?.close(); } catch { /* ignore */ }
        };
    }, [token, ingestAlert]);

    // ── REST polling fallback (catches alerts if WebSocket drops) ─────────
    useEffect(() => {
        if (!token) return undefined;

        let cancelled = false;

        async function pollRecentAlerts() {
            try {
                const res = await fetch(`${BACKEND}/api/alerts/recent?limit=20`, {
                    headers: { Authorization: `Bearer ${token}` },
                });
                if (!res.ok || cancelled) return;
                const body = await res.json();
                const items = Array.isArray(body?.alerts) ? body.alerts : [];
                for (let i = items.length - 1; i >= 0; i -= 1) {
                    ingestAlert(items[i]);
                }
            } catch {
                // ignore transient network errors
            }
        }

        pollRecentAlerts();
        const interval = setInterval(pollRecentAlerts, 5000);
        return () => {
            cancelled = true;
            clearInterval(interval);
        };
    }, [token, ingestAlert]);

    // ── Listen for alerts forwarded from the iframe via postMessage ────────
    useEffect(() => {
        mountedRef.current = true;

        function onMessage(evt) {
            if (!mountedRef.current) return;
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
                            <span className={`af-status-dot ${wsStatus === 'connected' ? 'af-status-dot--live' : ''}`} />
                            <span className="af-alerts-subtitle">
                                {wsStatus === 'connected'
                                    ? 'Live Monitoring'
                                    : wsStatus === 'connecting'
                                        ? 'Connecting…'
                                        : 'Reconnecting…'}
                            </span>
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

// ── Alert Category Mappings ──────────────────────────────────────────────────
const CATEGORY_META = {
    KNOWN_FACE: { label: 'Known Face', color: '#a855f7', dot: '🟣' },
    UNKNOWN_PERSON: { label: 'Unknown Person', color: '#3b82f6', dot: '🔵' },
    INTRUSION: { label: 'Intrusion', color: '#ef4444', dot: '🔴' },
    LOITERING: { label: 'Loitering', color: '#f97316', dot: '🟠' },
    PERSON: { label: 'Person', color: '#10b981', dot: '🟢' },
    VEHICLE: { label: 'Vehicle', color: '#06b6d4', dot: '🔵' },
    ROI_MOTION: { label: 'ROI / Motion', color: '#eab308', dot: '🟡' },
};

function getAlertCategory(alert) {
    const rawEvent = (alert.event || '').toUpperCase();
    const rawPerson = (alert.person || '').toLowerCase();
    
    if (alert.person && alert.person !== 'SYSTEM' && alert.person !== 'Object' && alert.person !== 'Unknown' && !alert.person.startsWith('Person-')) {
        return 'KNOWN_FACE';
    }
    if (rawEvent.includes('INTRUSION') || rawEvent.includes('LINE_CROSS') || rawEvent.includes('ZONE_ENTER') || rawEvent.includes('ZONE ENTER') || rawEvent.includes('CROSS')) {
        return 'INTRUSION';
    }
    if (rawEvent.includes('LOITERING')) {
        return 'LOITERING';
    }
    if (rawPerson === 'unknown' || rawPerson.startsWith('person-')) {
        return 'UNKNOWN_PERSON';
    }
    if (rawEvent.includes('VEHICLE') || rawEvent.includes('CAR') || rawEvent.includes('TRUCK') || rawEvent.includes('BUS') || rawEvent.includes('MOTORCYCLE')) {
        return 'VEHICLE';
    }
    if (rawPerson === 'person' || rawEvent.includes('PERSON')) {
        return 'PERSON';
    }
    if (rawEvent.includes('ROI') || rawEvent.includes('MOTION')) {
        return 'ROI_MOTION';
    }
    return 'PERSON';
}

// ── Alert Card ───────────────────────────────────────────────────────────────
function AlertCard({ alert, onAcknowledge }) {
    const category = getAlertCategory(alert);
    const meta = CATEGORY_META[category] || CATEGORY_META.PERSON;
    
    const { camera } = parseEventString(alert.event);
    const personLabel = formatPersonLabel(alert.person);
    const isAcknowledged = alert.acknowledged;
    const hasClip = Boolean(alert.clip_url);

    const [timeLabel, setTimeLabel] = useState(() => formatTimeAgo(alert.timestamp));

    useEffect(() => {
        const interval = setInterval(() => {
            setTimeLabel(formatTimeAgo(alert.timestamp));
        }, 1000);
        return () => clearInterval(interval);
    }, [alert.timestamp]);

    function handleReview() {
        if (!hasClip) return;
        window.open(alert.clip_url, '_blank', 'noopener,noreferrer');
    }

    return (
        <div 
            className={[
                'af-alert-card',
                alert.isNew ? 'af-alert-card--entering' : '',
                isAcknowledged ? 'af-alert-card--acknowledged' : '',
            ].filter(Boolean).join(' ')}
            style={{ borderLeft: `4px solid ${meta.color}` }}
        >
            <div className="af-alert-card-header" style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                <span className="af-alert-dot">{meta.dot}</span>
                <span className="af-alert-title-text" style={{ color: meta.color, fontWeight: '700', fontSize: '13px' }}>
                    {meta.label}
                </span>
                {personLabel && personLabel !== 'Unknown Person' && personLabel !== 'System Event' && (
                    <span className="af-alert-subtitle-text" style={{ fontSize: '12px', color: '#64748b' }}> ({personLabel})</span>
                )}
            </div>

            <div className="af-alert-details-row" style={{ fontSize: '12px', color: '#475569', fontWeight: '500' }}>
                {camera || 'Camera 1'} | {timeLabel}
            </div>

            {/* Actions */}
            {!isAcknowledged && (
                <div className="af-alert-actions" style={{ marginTop: '10px' }}>
                    <button
                        className="af-alert-btn af-alert-btn--primary"
                        onClick={() => onAcknowledge(alert.id)}
                        title="Mark as acknowledged"
                    >
                        <CheckCircle size={13} />
                        Acknowledge
                    </button>
                    <button
                        className={`af-alert-btn af-alert-btn--secondary ${!hasClip ? 'af-alert-btn--disabled' : ''}`}
                        onClick={handleReview}
                        disabled={!hasClip}
                        title={hasClip ? "Open event clip" : "No clip available"}
                    >
                        <PlayCircle size={13} />
                        Review
                    </button>
                </div>
            )}
        </div>
    );
}
