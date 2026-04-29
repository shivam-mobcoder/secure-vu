import { useState } from 'react';
import { CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import { enrollFrames } from '../services/faceServices';

/**
 * IdentityForm
 * Collects person details and submits enrollment request.
 */
export default function IdentityForm({ capturedFrames = [], enrolledNames = [], onSuccess, onCancel }) {
    const [form, setForm] = useState({
        name: '',
        email: '',
        role: 'employee',
        organization: '',
        notes: ''
    });
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
            // Include extra info in notes for the backend
            const combinedNotes = `Email: ${form.email} | Org: ${form.organization} | ${form.notes}`;
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
        setForm({ name: '', email: '', role: 'employee', organization: '', notes: '' });
        setConsent(false);
        if (onCancel) onCancel();
    }

    return (
        <form onSubmit={handleSubmit} style={styles.form}>
            {/* Name */}
            <div style={styles.field}>
                <label style={styles.label}>Full Name</label>
                <input
                    name="name"
                    type="text"
                    value={form.name}
                    onChange={handleChange}
                    placeholder="e.g. Jane Doe"
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

            {/* Email / ID */}
            <div style={styles.field}>
                <label style={styles.label}>Email / Employee ID</label>
                <input
                    name="email"
                    type="text"
                    value={form.email}
                    onChange={handleChange}
                    placeholder="jane.doe@company.com"
                    style={styles.input}
                />
            </div>

            {/* Role */}
            <div style={styles.field}>
                <label style={styles.label}>Role</label>
                <div style={styles.selectWrapper}>
                    <select name="role" value={form.role} onChange={handleChange} style={styles.input}>
                        <option value="employee">Employee</option>
                        <option value="contractor">Contractor</option>
                        <option value="visitor">Visitor</option>
                        <option value="vip">VIP</option>
                    </select>
                </div>
            </div>

            {/* Organization */}
            <div style={styles.field}>
                <label style={styles.label}>Organization (Optional)</label>
                <input
                    name="organization"
                    type="text"
                    value={form.organization}
                    onChange={handleChange}
                    placeholder="Department or Company"
                    style={styles.input}
                />
            </div>

            {/* Consent */}
            <div style={styles.consentWrapper}>
                <label style={styles.consent}>
                    <input
                        type="checkbox"
                        checked={consent}
                        onChange={e => setConsent(e.target.checked)}
                        style={styles.checkbox}
                    />
                    <div>
                        <div style={styles.consentLabel}>Biometric Data Consent</div>
                        <div style={styles.consentText}>
                            I agree to the collection and processing of my biometric data for security purposes.
                        </div>
                    </div>
                </label>
            </div>

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
                    type="submit"
                    style={{
                        ...styles.submitBtn,
                        opacity: (!hasFrames || status === 'loading' || status === 'success') ? 0.6 : 1,
                        cursor: (!hasFrames || status === 'loading' || status === 'success') ? 'not-allowed' : 'pointer',
                    }}
                    disabled={!hasFrames || status === 'loading' || status === 'success'}
                >
                    {status === 'loading' ? (
                        <><Loader2 size={15} style={{ animation: 'spin 1s linear infinite', marginRight: 8 }} />Processing…</>
                    ) : (
                        'Register Identity'
                    )}
                </button>
                <button
                    type="button"
                    onClick={handleCancel}
                    style={styles.cancelBtn}
                    disabled={status === 'loading'}
                >
                    Cancel
                </button>
            </div>
        </form>
    );
}

const styles = {
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
        transition: 'all 0.2s',
        width: '100%',
        boxSizing: 'border-box',
        '&:focus': {
            borderColor: '#3b82f6',
            background: '#ffffff',
            boxShadow: '0 0 0 3px rgba(59, 130, 246, 0.1)',
        }
    },
    selectWrapper: {
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
    },
    consentWrapper: {
        padding: '16px',
        background: '#f8fafc',
        borderRadius: 12,
        border: '1px solid #e2e8f0',
    },
    consent: {
        display: 'flex',
        gap: 12,
        cursor: 'pointer',
    },
    checkbox: {
        marginTop: '3px',
        width: '16px',
        height: '16px',
        accentColor: '#000000',
    },
    consentLabel: {
        fontSize: 13,
        fontWeight: 700,
        color: '#1e293b',
    },
    consentText: {
        fontSize: 12,
        color: '#64748b',
        lineHeight: 1.5,
        marginTop: 2,
    },
    successMsg: {
        display: 'flex',
        alignItems: 'flex-start',
        gap: 4,
        background: '#f0fdf4',
        border: '1px solid #bbf7d0',
        color: '#166534',
        borderRadius: 8,
        padding: '12px',
        fontSize: 13,
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
    buttonRow: {
        display: 'flex',
        gap: 12,
        marginTop: 8,
    },
    submitBtn: {
        flex: 1,
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
    cancelBtn: {
        flex: 1,
        padding: '14px 24px',
        borderRadius: 8,
        border: '1px solid #e2e8f0',
        background: '#ffffff',
        color: '#1e293b',
        fontSize: 14,
        fontWeight: 600,
        cursor: 'pointer',
        textAlign: 'center',
        transition: 'all 0.2s',
    },
};
