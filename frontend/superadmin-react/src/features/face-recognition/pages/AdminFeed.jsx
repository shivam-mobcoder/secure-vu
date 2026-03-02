import { useEffect, useRef, useState } from 'react';
import { ExternalLink, RefreshCw, Video, RadioTower, Filter, Clock, Shield } from 'lucide-react';
import { getStoredToken } from '../../../auth';
import '../../../styles/adminfeed.css';

/**
 * AdminFeed
 * Embeds the existing live CCTV client.html viewer inside an iframe,
 * passing the current JWT token so the feed is authenticated.
 * This reuses 100% of the existing WebRTC/streaming logic.
 */

// Mock alerts data for the Security Alerts sidebar
const MOCK_ALERTS = [
    {
        id: 1,
        status: 'new',
        title: 'Watchlist Match Detected',
        confidence: 98,
        time: 'Just now',
        location: 'North Entrance',
        locationId: 'WL-001',
    },
    {
        id: 2,
        status: 'new',
        title: 'Watchlist Match Detected',
        confidence: 85,
        time: '2 mins ago',
        location: 'Parking Garage B',
        locationId: 'WL-002',
    },
    {
        id: 3,
        status: 'acknowledged',
        title: 'Watchlist Match Detected',
        confidence: 92,
        time: '8 mins ago',
        location: 'Lobby Main',
        locationId: 'WL-003',
    },
];

export default function AdminFeed() {
    const iframeRef = useRef(null);
    const [loading, setLoading] = useState(true);
    const [key, setKey] = useState(0); // bump to reload iframe

    // Build the URL — point to the original CCTV viewer page.
    // The static route is served by aiohttp and whitelisted in middleware.
    const token = getStoredToken();
    const BACKEND = import.meta.env.VITE_BACKEND_ORIGIN || '';
    const feedUrl = token
        ? `${BACKEND}/static/client.html?token=${encodeURIComponent(token)}`
        : `${BACKEND}/static/client.html`;

    function handleReload() {
        setLoading(true);
        setKey(k => k + 1);
    }

    function handleOpenInTab() {
        window.open(feedUrl, '_blank', 'noopener,noreferrer');
    }

    return (
        <div className="af-page">
            {/* ── Left: Feed Area ──────────────────────────── */}
            <div className="af-feed-area">
                {/* Main Feed */}
                <div className="af-main-feed">
                    {/* Overlay: Status Badges */}
                    <div className="af-feed-overlay">
                        <span className="af-live-badge">
                            <Shield size={14} />
                            Live Monitoring Active
                        </span>
                        <span className="af-quality-badge">
                            <span className="af-quality-dot" />
                            Quality: Good
                        </span>
                    </div>

                    {/* Grid lines overlay */}
                    <div className="af-grid-overlay">
                        <div className="af-grid-line-v" style={{ left: '25%' }} />
                        <div className="af-grid-line-v" style={{ left: '50%' }} />
                        <div className="af-grid-line-v" style={{ left: '75%' }} />
                        <div className="af-grid-line-h" style={{ top: '33%' }} />
                        <div className="af-grid-line-h" style={{ top: '66%' }} />
                    </div>

                    {/* Loading State */}
                    {loading && (
                        <div className="af-loading-overlay">
                            <Video size={36} color="#22c55e" style={{ animation: 'af-pulse 1.5s ease-in-out infinite' }} />
                            <p className="af-loading-text">Connecting to camera feed…</p>
                        </div>
                    )}

                    {/* The actual iframe — logic fully preserved */}
                    <iframe
                        key={key}
                        ref={iframeRef}
                        src={feedUrl}
                        style={{ opacity: loading ? 0 : 1 }}
                        title="Live Camera Feed"
                        allow="camera; microphone; autoplay"
                        onLoad={() => setLoading(false)}
                        onError={() => setLoading(false)}
                    />
                </div>

                {/* Secondary Camera Slots */}
                <div className="af-secondary-feeds">
                    <div className="af-cam-slot">[ CAM 02 FEED ]</div>
                    <div className="af-cam-slot">[ CAM 03 FEED ]</div>
                </div>
            </div>

            {/* ── Right: Security Alerts Sidebar ─────────── */}
            <div className="af-alerts-sidebar">
                <div className="af-alerts-header">
                    <div>
                        <h2 className="af-alerts-title">Security Alerts</h2>
                        <p className="af-alerts-subtitle">Real-time watchlist notifications</p>
                    </div>
                    <div className="af-alerts-actions">
                        <button className="af-alerts-icon-btn" title="Filter alerts">
                            <Filter size={15} />
                        </button>
                        <button className="af-alerts-icon-btn" title="Refresh feed" onClick={handleReload}>
                            <RefreshCw size={15} />
                        </button>
                    </div>
                </div>

                <div className="af-alerts-list">
                    {MOCK_ALERTS.map(alert => (
                        <div key={alert.id} className="af-alert-card">
                            {/* Header: Badge + Confidence */}
                            <div className="af-alert-top">
                                <span className={`af-alert-badge ${alert.status === 'new' ? 'af-alert-badge--new' : 'af-alert-badge--ack'}`}>
                                    {alert.status === 'new' ? 'NEW ALERT' : 'ACKNOWLEDGED'}
                                </span>
                                <div className="af-alert-confidence">
                                    <div className="af-alert-confidence-value">{alert.confidence}%</div>
                                    <div className="af-alert-confidence-label">Confidence</div>
                                </div>
                            </div>

                            {/* Title + Time */}
                            <div className="af-alert-title">{alert.title}</div>
                            <div className="af-alert-time">
                                <Clock size={12} />
                                {alert.time}
                            </div>

                            {/* Location */}
                            <div className="af-alert-location">
                                <div className="af-alert-location-img">IMG</div>
                                <div>
                                    <div className="af-alert-location-name">{alert.location}</div>
                                    <div className="af-alert-location-id">ID: {alert.locationId}</div>
                                </div>
                            </div>

                            {/* Actions */}
                            <div className="af-alert-actions">
                                <button className="af-alert-btn af-alert-btn--primary">Acknowledge</button>
                                <button className="af-alert-btn af-alert-btn--secondary">Review</button>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
}
