import { useEffect, useRef, useState } from 'react';
import { ExternalLink, RefreshCw, Video, RadioTower } from 'lucide-react';
import { getStoredToken } from '../../../auth';

/**
 * AdminFeed
 * Embeds the existing live CCTV client.html viewer inside an iframe,
 * passing the current JWT token so the feed is authenticated.
 * This reuses 100% of the existing WebRTC/streaming logic.
 */
export default function AdminFeed() {
    const iframeRef = useRef(null);
    const [loading, setLoading] = useState(true);
    const [key, setKey] = useState(0); // bump to reload iframe

    // Build the URL — in dev mode route through Vite proxy to avoid mixed content;
    // in production the backend and frontend share the same origin.
    const token = getStoredToken();
    const isDev = !import.meta.env.VITE_BACKEND_ORIGIN;
    const backendOrigin = isDev
        ? ''   // same-origin — goes through Vite proxy
        : import.meta.env.VITE_BACKEND_ORIGIN;

    // In dev: /backend-client proxies to the backend's root '/' (client.html)
    const basePath = isDev ? '/backend-client' : '/';
    const feedUrl = token
        ? `${backendOrigin}${basePath}?token=${encodeURIComponent(token)}`
        : `${backendOrigin}${basePath}`;

    function handleReload() {
        setLoading(true);
        setKey(k => k + 1);
    }

    function handleOpenInTab() {
        window.open(feedUrl, '_blank', 'noopener,noreferrer');
    }

    return (
        <div style={s.page}>
            {/* Header bar */}
            <div style={s.header}>
                <div style={s.titleGroup}>
                    <RadioTower size={20} color="#22c55e" />
                    <div>
                        <h1 style={s.title}>Live Camera Feed</h1>
                        <p style={s.subtitle}>Real-time CCTV stream with AI analytics</p>
                    </div>
                </div>

                <div style={s.headerActions}>
                    {/* Live indicator */}
                    <span style={s.liveBadge}>
                        <span style={s.liveDot} />
                        LIVE
                    </span>

                    <button onClick={handleReload} style={s.iconBtn} title="Reload feed">
                        <RefreshCw size={15} />
                    </button>
                    <button onClick={handleOpenInTab} style={s.iconBtn} title="Open in new tab">
                        <ExternalLink size={15} />
                    </button>
                </div>
            </div>

            {/* Iframe container */}
            <div style={s.iframeWrapper}>
                {loading && (
                    <div style={s.loadingOverlay}>
                        <Video size={36} color="#22c55e" style={{ animation: 'pulse 1.5s ease-in-out infinite' }} />
                        <p style={s.loadingText}>Connecting to camera feed…</p>
                    </div>
                )}
                <iframe
                    key={key}
                    ref={iframeRef}
                    src={feedUrl}
                    style={{
                        ...s.iframe,
                        opacity: loading ? 0 : 1,
                    }}
                    title="Live Camera Feed"
                    allow="camera; microphone; autoplay"
                    onLoad={() => setLoading(false)}
                    onError={() => setLoading(false)}
                />
            </div>

            <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50%       { opacity: 0.4; }
        }
        @keyframes blink {
          0%, 100% { opacity: 1; }
          50%       { opacity: 0.2; }
        }
      `}</style>
        </div>
    );
}

const s = {
    page: {
        display: 'flex',
        flexDirection: 'column',
        gap: 16,
        height: 'calc(100vh - 48px)',  // fill the main content area
        background: '#0a0f1e',
        padding: 0,
        margin: -32,       // cancel the layout's p-8 padding so feed goes edge-to-edge
        fontFamily: "'Inter', system-ui, sans-serif",
    },
    header: {
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '16px 24px',
        background: '#0f172a',
        borderBottom: '1px solid #1e293b',
        flexShrink: 0,
    },
    titleGroup: {
        display: 'flex',
        alignItems: 'center',
        gap: 12,
    },
    title: {
        margin: 0,
        fontSize: 18,
        fontWeight: 800,
        color: '#f1f5f9',
        letterSpacing: '-0.02em',
    },
    subtitle: {
        margin: 0,
        fontSize: 12,
        color: '#64748b',
    },
    headerActions: {
        display: 'flex',
        alignItems: 'center',
        gap: 10,
    },
    liveBadge: {
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        background: 'rgba(34,197,94,0.12)',
        border: '1px solid rgba(34,197,94,0.35)',
        color: '#86efac',
        fontSize: 11,
        fontWeight: 700,
        letterSpacing: '0.08em',
        padding: '4px 10px',
        borderRadius: 99,
    },
    liveDot: {
        width: 7,
        height: 7,
        borderRadius: '50%',
        background: '#22c55e',
        animation: 'blink 1.2s ease-in-out infinite',
        display: 'inline-block',
    },
    iconBtn: {
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: 34,
        height: 34,
        borderRadius: 8,
        border: '1px solid #1e293b',
        background: 'rgba(255,255,255,0.04)',
        color: '#94a3b8',
        cursor: 'pointer',
        transition: 'background 0.15s',
    },
    iframeWrapper: {
        flex: 1,
        position: 'relative',
        background: '#000',
        overflow: 'hidden',
    },
    loadingOverlay: {
        position: 'absolute',
        inset: 0,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#000',
        gap: 14,
        zIndex: 2,
    },
    loadingText: {
        margin: 0,
        color: '#64748b',
        fontSize: 14,
    },
    iframe: {
        width: '100%',
        height: '100%',
        border: 'none',
        display: 'block',
        transition: 'opacity 0.4s',
    },
};
