import { useState, useCallback, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { ShieldCheck, CheckCircle2, XCircle, Loader2, AlertTriangle } from 'lucide-react';
import CapturePanel from '../components/CapturePanel';
import { validateEnrollToken, enrollWithToken } from '../services/faceServices';

/**
 * SelfEnrollment — public page at /enroll/:token
 * Lets anyone with a valid share link enroll their face without logging in.
 */
export default function SelfEnrollment() {
    const { token } = useParams();

    const [tokenStatus, setTokenStatus] = useState('checking'); // checking | valid | invalid
    const [capturedFrames, setCapturedFrames] = useState([]);
    const [name, setName] = useState('');
    const [status, setStatus] = useState('idle');   // idle | loading | success | error
    const [message, setMessage] = useState('');
    const [livenessScore, setLivenessScore] = useState(null);

    // Validate token on mount
    useEffect(() => {
        (async () => {
            try {
                const res = await validateEnrollToken(token);
                setTokenStatus(res.valid ? 'valid' : 'invalid');
            } catch {
                setTokenStatus('invalid');
            }
        })();
    }, [token]);

    const handleCapture = useCallback((frames) => {
        setCapturedFrames(frames);
    }, []);

    const handleReset = useCallback(() => {
        setCapturedFrames([]);
    }, []);

    async function handleSubmit(e) {
        e.preventDefault();
        if (!capturedFrames.length || !name.trim()) return;

        setStatus('loading');
        setMessage('');
        setLivenessScore(null);

        try {
            const result = await enrollWithToken(token, name.trim(), capturedFrames);
            setLivenessScore(result.liveness_score ?? null);
            if (result.status === 'ok') {
                setStatus('success');
                setMessage(result.message || 'Face enrolled successfully!');
            } else {
                setStatus('error');
                setMessage(result.message || 'Enrollment failed.');
            }
        } catch (err) {
            setStatus('error');
            setMessage(err.message || 'Enrollment failed. Please try again.');
        }
    }

    // ── Invalid / expired state ──────────────────────────────────────────────
    if (tokenStatus === 'checking') {
        return (
            <div style={s.page}>
                <div style={s.centerCard}>
                    <Loader2 size={40} style={{ animation: 'spin 1s linear infinite', color: '#3b82f6' }} />
                    <p style={s.loadingText}>Validating enrollment link…</p>
                    <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
                </div>
            </div>
        );
    }

    if (tokenStatus === 'invalid') {
        return (
            <div style={s.page}>
                <div style={s.centerCard}>
                    <AlertTriangle size={48} color="#f59e0b" />
                    <h2 style={s.expiredTitle}>Link Expired or Invalid</h2>
                    <p style={s.expiredText}>
                        This enrollment link has expired or has already been used.
                        Please ask your administrator for a new link.
                    </p>
                </div>
            </div>
        );
    }

    // ── Success state ────────────────────────────────────────────────────────
    if (status === 'success') {
        return (
            <div style={s.page}>
                <div style={s.centerCard}>
                    <CheckCircle2 size={56} color="#22c55e" />
                    <h2 style={{ ...s.expiredTitle, color: '#22c55e' }}>Enrollment Complete!</h2>
                    <p style={s.expiredText}>{message}</p>
                    {livenessScore !== null && (
                        <p style={{ color: '#64748b', fontSize: 12, marginTop: 4 }}>
                            Liveness score: {(livenessScore * 100).toFixed(0)}%
                        </p>
                    )}
                    <p style={{ color: '#475569', fontSize: 13, marginTop: 16 }}>
                        You can close this tab now.
                    </p>
                </div>
            </div>
        );
    }

    // ── Main enrollment flow ─────────────────────────────────────────────────
    const hasFrames = capturedFrames.length > 0;

    return (
        <div style={s.page}>
            {/* Header */}
            <div style={s.header}>
                <ShieldCheck size={24} color="#22c55e" />
                <div>
                    <h1 style={s.title}>Face Enrollment</h1>
                    <p style={s.subtitle}>
                        Follow the guided scan to register your face for biometric access.
                    </p>
                </div>
            </div>

            {/* Camera */}
            <div style={s.section}>
                <p style={s.stepLabel}>Step 1 — Face Scan</p>
                <CapturePanel onCapture={handleCapture} onReset={handleReset} />
            </div>

            {/* Form */}
            <div style={s.section}>
                <p style={s.stepLabel}>Step 2 — Your Details</p>
                <form onSubmit={handleSubmit} style={s.form}>
                    <div style={s.field}>
                        <label style={s.label}>Full Name *</label>
                        <input
                            type="text"
                            value={name}
                            onChange={e => setName(e.target.value)}
                            placeholder="e.g. Ritik Sharma"
                            required
                            style={s.input}
                        />
                    </div>

                    {/* Frame badge */}
                    <div style={{
                        ...s.badge,
                        borderColor: hasFrames ? '#22c55e44' : '#ef444444',
                        color: hasFrames ? '#86efac' : '#fca5a5',
                        background: hasFrames ? 'rgba(34,197,94,0.08)' : 'rgba(239,68,68,0.08)',
                    }}>
                        {hasFrames
                            ? `✓ ${capturedFrames.length} poses captured`
                            : '⚠ No frames captured yet — use the camera above'}
                    </div>

                    {/* Error */}
                    {status === 'error' && (
                        <div style={s.errorMsg}>
                            <XCircle size={16} style={{ marginRight: 6, flexShrink: 0 }} />
                            {message}
                        </div>
                    )}

                    <button
                        type="submit"
                        disabled={!hasFrames || !name.trim() || status === 'loading'}
                        style={{
                            ...s.submitBtn,
                            opacity: (!hasFrames || !name.trim() || status === 'loading') ? 0.5 : 1,
                            cursor: (!hasFrames || !name.trim() || status === 'loading') ? 'not-allowed' : 'pointer',
                        }}
                    >
                        {status === 'loading' ? (
                            <>
                                <Loader2 size={15} style={{ animation: 'spin 1s linear infinite', marginRight: 6 }} />
                                Enrolling…
                            </>
                        ) : (
                            'Register Face'
                        )}
                    </button>
                </form>
            </div>

            <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
    );
}

// ── Styles ───────────────────────────────────────────────────────────────────
const s = {
    page: {
        minHeight: '100vh',
        background: '#0a0f1e',
        padding: '24px',
        fontFamily: "'Inter', system-ui, sans-serif",
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 20,
    },
    header: {
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        width: '100%',
        maxWidth: 560,
    },
    title: {
        margin: 0,
        fontSize: 22,
        fontWeight: 800,
        color: '#f1f5f9',
        letterSpacing: '-0.02em',
    },
    subtitle: {
        margin: '4px 0 0',
        fontSize: 13,
        color: '#64748b',
        lineHeight: 1.5,
    },
    section: {
        width: '100%',
        maxWidth: 560,
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
    },
    stepLabel: {
        margin: 0,
        fontSize: 11,
        fontWeight: 700,
        textTransform: 'uppercase',
        letterSpacing: '0.08em',
        color: '#475569',
    },
    form: {
        display: 'flex',
        flexDirection: 'column',
        gap: 14,
        background: '#0f172a',
        borderRadius: 16,
        padding: 20,
        boxShadow: '0 4px 32px rgba(0,0,0,0.4)',
    },
    field: {
        display: 'flex',
        flexDirection: 'column',
        gap: 5,
    },
    label: {
        fontSize: 12,
        fontWeight: 600,
        color: '#94a3b8',
        textTransform: 'uppercase',
        letterSpacing: '0.04em',
    },
    input: {
        padding: '9px 12px',
        borderRadius: 8,
        border: '1px solid #1e293b',
        background: '#1e293b',
        color: '#e2e8f0',
        fontSize: 14,
        outline: 'none',
        width: '100%',
        boxSizing: 'border-box',
    },
    badge: {
        fontSize: 12,
        fontWeight: 500,
        padding: '7px 12px',
        borderRadius: 8,
        border: '1px solid',
        textAlign: 'center',
    },
    errorMsg: {
        display: 'flex',
        alignItems: 'center',
        background: 'rgba(239,68,68,0.08)',
        border: '1px solid rgba(239,68,68,0.3)',
        color: '#fca5a5',
        borderRadius: 8,
        padding: '10px 12px',
        fontSize: 13,
    },
    submitBtn: {
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '12px 20px',
        borderRadius: 10,
        border: 'none',
        background: 'linear-gradient(135deg, #3b82f6, #6366f1)',
        color: '#fff',
        fontSize: 14,
        fontWeight: 700,
        transition: 'opacity 0.2s',
    },
    centerCard: {
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 16,
        background: '#0f172a',
        borderRadius: 20,
        padding: '48px 40px',
        boxShadow: '0 8px 40px rgba(0,0,0,0.5)',
        maxWidth: 420,
        margin: 'auto',
        textAlign: 'center',
    },
    loadingText: {
        color: '#94a3b8',
        fontSize: 15,
        margin: 0,
    },
    expiredTitle: {
        margin: 0,
        color: '#f59e0b',
        fontSize: 20,
        fontWeight: 800,
    },
    expiredText: {
        margin: 0,
        color: '#94a3b8',
        fontSize: 14,
        lineHeight: 1.6,
        maxWidth: 320,
    },
};
