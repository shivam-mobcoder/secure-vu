import { useState } from 'react';
import { User, Mail, Tag, Loader2, CheckCircle2, XCircle, Shield } from 'lucide-react';
import { enrollFrames } from '../services/faceServices';

/**
 * IdentityForm
 * Collects person details and submits enrollment request.
 *
 * Props:
 *   capturedFrames: string[] — base64 data-URIs from CapturePanel
 *   onSuccess() — called after successful enrollment
 *   onCancel() — called when user cancels
 */
export default function IdentityForm({ capturedFrames = [], enrolledNames = [], onSuccess, onCancel }) {
    const [form, setForm] = useState({ name: '', role: 'employee', notes: '' });
    const [status, setStatus] = useState('idle');   // idle | loading | success | error
    const [message, setMessage] = useState('');
    const [livenessScore, setLivenessScore] = useState(null);
    const [consent, setConsent] = useState(false);

    const hasFrames = capturedFrames.length > 0;

    function handleChange(e) {
        setForm(prev => ({ ...prev, [e.target.name]: e.target.value }));
    }

    async function handleSubmit(e) {
        e.preventDefault();
        if (!hasFrames) {
            setStatus('error');
            setMessage('Please capture webcam frames first.');
            return;
        }
        if (!consent) {
            setStatus('error');
            setMessage('You must agree to biometric data processing.');
            return;
        }
        if (!form.name.trim()) {
            setStatus('error');
            setMessage('Name is required.');
            return;
        }

        setStatus('loading');
        setMessage('');
        setLivenessScore(null);

        try {
            const result = await enrollFrames(form.name.trim(), capturedFrames);
            setLivenessScore(result.liveness_score ?? null);
            if (result.status === 'ok') {
                setStatus('success');
                setMessage(result.message || 'Face enrolled successfully!');
                if (onSuccess) onSuccess(form.name.trim());
            } else {
                setStatus('error');
                setMessage(result.message || 'Enrollment failed.');
            }
        } catch (err) {
            setStatus('error');
            setMessage(err.message || 'Enrollment failed. Please try again.');
        }
    }

    function handleCancel() {
        setStatus('idle');
        setMessage('');
        setForm({ name: '', role: 'employee', notes: '' });
        setConsent(false);
        if (onCancel) onCancel();
    }

    return (
        <form onSubmit={handleSubmit} style={styles.form}>
            <h3 style={styles.heading}>Person Details</h3>

            {/* Name */}
            <div style={styles.field}>
                <label style={styles.label}>
                    <User size={13} style={{ marginRight: 4 }} />Full Name *
                </label>
                <input
                    name="name"
                    type="text"
                    value={form.name}
                    onChange={handleChange}
                    placeholder="e.g. Ritik Sharma"
                    required
                    style={styles.input}
                    list="enrolled-names-list"
                />
                <datalist id="enrolled-names-list">
                    {enrolledNames.map(n => (
                        <option key={n} value={n} />
                    ))}
                </datalist>
            </div>

            {/* Re-enrollment notice */}
            {form.name.trim() && enrolledNames.includes(form.name.trim()) && (
                <div style={styles.reEnrollNotice}>
                    Adding more data to existing profile for <strong>{form.name.trim()}</strong>.
                    This improves recognition accuracy.
                </div>
            )}

            {/* Role */}
            <div style={styles.field}>
                <label style={styles.label}>
                    <Tag size={13} style={{ marginRight: 4 }} />Role
                </label>
                <select name="role" value={form.role} onChange={handleChange} style={styles.input}>
                    <option value="employee">Employee</option>
                    <option value="contractor">Contractor</option>
                    <option value="visitor">Visitor</option>
                    <option value="vip">VIP</option>
                </select>
            </div>

            {/* Notes (optional) */}
            <div style={styles.field}>
                <label style={styles.label}>
                    <Mail size={13} style={{ marginRight: 4 }} />Notes (optional)
                </label>
                <input
                    name="notes"
                    type="text"
                    value={form.notes}
                    onChange={handleChange}
                    placeholder="Dept, ID, email…"
                    style={styles.input}
                />
            </div>

            {/* Consent */}
            <label style={styles.consent}>
                <input
                    type="checkbox"
                    checked={consent}
                    onChange={e => setConsent(e.target.checked)}
                    style={{ marginRight: 8, accentColor: '#22c55e' }}
                />
                <Shield size={13} style={{ marginRight: 4, color: '#22c55e' }} />
                I consent to biometric face data being processed and stored securely.
            </label>

            {/* Frame count badge */}
            {status !== 'success' && (
                <div style={{
                    ...styles.frameBadge,
                    borderColor: hasFrames ? '#22c55e44' : '#ef444444',
                    color: hasFrames ? '#86efac' : '#fca5a5',
                    background: hasFrames ? 'rgba(34,197,94,0.08)' : 'rgba(239,68,68,0.08)',
                }}>
                    {hasFrames
                        ? `✓ ${capturedFrames.length} frame${capturedFrames.length !== 1 ? 's' : ''} ready`
                        : '⚠ No frames captured yet — click \"Begin Capture\" in Step 1 first'}
                </div>
            )}

            {/* Status message */}
            {status === 'success' && (
                <div style={styles.successMsg}>
                    <CheckCircle2 size={16} style={{ marginRight: 6, flexShrink: 0 }} />
                    <div>
                        <div>{message}</div>
                        {livenessScore !== null && (
                            <div style={{ fontSize: 11, marginTop: 2, opacity: 0.8 }}>
                                Liveness score: {(livenessScore * 100).toFixed(0)}%
                            </div>
                        )}
                    </div>
                </div>
            )}
            {status === 'error' && (
                <div style={styles.errorMsg}>
                    <XCircle size={16} style={{ marginRight: 6, flexShrink: 0 }} />
                    {message}
                </div>
            )}

            {/* Buttons */}
            <div style={styles.buttonRow}>
                <button
                    type="button"
                    onClick={handleCancel}
                    style={styles.cancelBtn}
                    disabled={status === 'loading'}
                >
                    Cancel
                </button>
                <button
                    type="submit"
                    style={{
                        ...styles.submitBtn,
                        opacity: (!hasFrames || status === 'loading' || status === 'success') ? 0.6 : 1,
                        cursor: (!hasFrames || status === 'loading' || status === 'success') ? 'not-allowed' : 'pointer',
                    }}
                    disabled={!hasFrames || status === 'loading' || status === 'success'}
                >
                    {status === 'loading' ? (
                        <><Loader2 size={15} style={{ animation: 'spin 1s linear infinite', marginRight: 6 }} />Enrolling…</>
                    ) : status === 'success' ? (
                        <><CheckCircle2 size={15} style={{ marginRight: 6 }} />Enrolled!</>
                    ) : (
                        'Register Face'
                    )}
                </button>
            </div>
        </form>
    );
}

const styles = {
    form: {
        display: 'flex',
        flexDirection: 'column',
        gap: 14,
        background: '#0f172a',
        borderRadius: 16,
        padding: 20,
        boxShadow: '0 4px 32px rgba(0,0,0,0.4)',
    },
    heading: {
        margin: 0,
        fontSize: 15,
        fontWeight: 700,
        color: '#e2e8f0',
    },
    field: {
        display: 'flex',
        flexDirection: 'column',
        gap: 5,
    },
    label: {
        display: 'inline-flex',
        alignItems: 'center',
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
        transition: 'border-color 0.2s',
        width: '100%',
        boxSizing: 'border-box',
    },
    consent: {
        display: 'flex',
        alignItems: 'center',
        fontSize: 12,
        color: '#64748b',
        cursor: 'pointer',
        lineHeight: 1.4,
    },
    frameBadge: {
        fontSize: 12,
        fontWeight: 500,
        padding: '7px 12px',
        borderRadius: 8,
        border: '1px solid',
        textAlign: 'center',
    },
    successMsg: {
        display: 'flex',
        alignItems: 'flex-start',
        gap: 4,
        background: 'rgba(34,197,94,0.08)',
        border: '1px solid rgba(34,197,94,0.3)',
        color: '#86efac',
        borderRadius: 8,
        padding: '10px 12px',
        fontSize: 13,
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
    buttonRow: {
        display: 'flex',
        gap: 8,
        marginTop: 4,
    },
    cancelBtn: {
        flex: 1,
        padding: '10px',
        borderRadius: 10,
        border: '1px solid #334155',
        background: 'transparent',
        color: '#94a3b8',
        fontSize: 14,
        fontWeight: 600,
        cursor: 'pointer',
    },
    submitBtn: {
        flex: 2,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '10px 20px',
        borderRadius: 10,
        border: 'none',
        background: 'linear-gradient(135deg, #3b82f6, #6366f1)',
        color: '#fff',
        fontSize: 14,
        fontWeight: 700,
        transition: 'opacity 0.2s',
    },
    reEnrollNotice: {
        fontSize: 12,
        color: '#93c5fd',
        background: 'rgba(59,130,246,0.08)',
        border: '1px solid rgba(59,130,246,0.25)',
        borderRadius: 8,
        padding: '8px 12px',
        lineHeight: 1.5,
    },
};
