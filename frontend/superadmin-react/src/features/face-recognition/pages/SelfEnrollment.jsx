import { useState, useCallback, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { ShieldCheck, CheckCircle2, XCircle, Loader2, AlertTriangle, Shield } from 'lucide-react';
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
                <ShieldCheck size={28} color="#22c55e" />
                <div>
                    <h1 style={s.title}>Face Enrollment</h1>
                    <p style={s.subtitle}>
                        Follow the guided scan to register your face for biometric access.
                    </p>
                </div>
            </div>

            {/* Layout Grid */}
            <div style={s.layoutGrid}>
                {/* Camera */}
                <div style={s.card}>
                    <div style={s.cardHeader}>
                        <h2 style={s.cardTitle}>Live Capture</h2>
                        <p style={s.cardSubtitle}>Position face within the frame and ensure good lighting.</p>
                    </div>
                    <div style={s.cardContent}>
                        <CapturePanel onCapture={handleCapture} onReset={handleReset} />
                    </div>
                </div>

                {/* Form */}
                <div style={s.card}>
                    <div style={s.cardHeader}>
                        <h2 style={s.cardTitle}>Your Details</h2>
                        <p style={s.cardSubtitle}>Associate biometric data with your identity.</p>
                    </div>
                    <div style={s.cardContent}>
                        <form onSubmit={handleSubmit} style={s.form}>
                            <div style={s.field}>
                                <label style={s.label}>Full Name</label>
                                <input
                                    type="text"
                                    value={name}
                                    onChange={e => setName(e.target.value)}
                                    placeholder="e.g. Jane Doe"
                                    required
                                    style={s.input}
                                />
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
                                    opacity: (!hasFrames || !name.trim() || status === 'loading') ? 0.6 : 1,
                                    cursor: (!hasFrames || !name.trim() || status === 'loading') ? 'not-allowed' : 'pointer',
                                }}
                            >
                                {status === 'loading' ? (
                                    <>
                                        <Loader2 size={15} style={{ animation: 'spin 1s linear infinite', marginRight: 8 }} />
                                        Processing…
                                    </>
                                ) : (
                                    'Register Identity'
                                )}
                            </button>
                        </form>
                    </div>
                </div>
            </div>

            {/* Privacy Banner */}
            <div style={s.privacyBanner}>
                <Shield size={18} color="#64748b" />
                <p style={s.privacyText}>
                    Biometric templates are irreversibly hashed and encrypted. Raw imagery is not stored.
                </p>
            </div>

            <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
    );
}

// ── Styles ───────────────────────────────────────────────────────────────────
const s = {
    page: {
        minHeight: '100vh',
        background: '#f8fafc',
        padding: '32px 24px',
        fontFamily: "'Inter', system-ui, sans-serif",
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 32,
    },
    header: {
        display: 'flex',
        alignItems: 'center',
        gap: 16,
        width: '100%',
        maxWidth: 1000,
        borderBottom: '1px solid #e2e8f0',
        paddingBottom: '24px',
    },
    title: {
        margin: 0,
        fontSize: 24,
        fontWeight: 700,
        color: '#0f172a',
        letterSpacing: '-0.02em',
    },
    subtitle: {
        margin: '4px 0 0',
        fontSize: 14,
        color: '#64748b',
    },
    layoutGrid: {
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))',
        gap: 32,
        width: '100%',
        maxWidth: 1000,
        alignItems: 'start',
    },
    card: {
        background: '#ffffff',
        borderRadius: 12,
        border: '1px solid #e2e8f0',
        boxShadow: '0 4px 6px -1px rgba(0,0,0,0.05)',
        overflow: 'hidden',
    },
    cardHeader: {
        padding: '24px',
        borderBottom: '1px solid #f1f5f9',
    },
    cardTitle: {
        margin: 0,
        fontSize: 16,
        fontWeight: 700,
        color: '#1e293b',
    },
    cardSubtitle: {
        margin: '4px 0 0',
        fontSize: 13,
        color: '#94a3b8',
    },
    cardContent: {
        padding: '24px',
    },
    form: {
        display: 'flex',
        flexDirection: 'column',
        gap: 20,
    },
    field: {
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
    },
    label: {
        fontSize: 13,
        fontWeight: 600,
        color: '#1e293b',
    },
    input: {
        padding: '12px 16px',
        borderRadius: 8,
        border: '1px solid #e2e8f0',
        background: '#f8fafc',
        color: '#1e293b',
        fontSize: 14,
        outline: 'none',
        width: '100%',
        boxSizing: 'border-box',
    },
    errorMsg: {
        display: 'flex',
        alignItems: 'center',
        background: '#fef2f2',
        border: '1px solid #fecaca',
        color: '#991b1b',
        borderRadius: 8,
        padding: '12px',
        fontSize: 13,
    },
    submitBtn: {
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '14px 24px',
        borderRadius: 8,
        border: 'none',
        background: '#000000',
        color: '#ffffff',
        fontSize: 14,
        fontWeight: 700,
        transition: 'all 0.2s',
    },
    centerCard: {
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 16,
        background: '#ffffff',
        border: '1px solid #e2e8f0',
        borderRadius: 16,
        padding: '48px 40px',
        boxShadow: '0 10px 15px -3px rgba(0,0,0,0.1)',
        maxWidth: 420,
        margin: 'auto',
        textAlign: 'center',
    },
    loadingText: {
        color: '#64748b',
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
        color: '#64748b',
        fontSize: 14,
        lineHeight: 1.6,
        maxWidth: 320,
    },
    privacyBanner: {
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        color: '#64748b',
        fontSize: 12,
        maxWidth: 1000,
        width: '100%',
        justifyContent: 'center',
    },
    privacyText: {
        margin: 0,
    },
};
