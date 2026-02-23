import { useState, useCallback, useEffect } from 'react';
import { Link2, Copy, Check, X, Users, Trash2, RefreshCw, ShieldCheck } from 'lucide-react';
import CapturePanel from '../components/CapturePanel';
import IdentityForm from '../components/IdentityForm';
import { createEnrollLink, listFaces, deleteFace } from '../services/faceServices';

export default function FaceEnrollment() {
  const [capturedFrames, setCapturedFrames] = useState([]);
  const [showLinkModal, setShowLinkModal] = useState(false);
  const [enrollLink, setEnrollLink] = useState('');
  const [linkLoading, setLinkLoading] = useState(false);
  const [linkError, setLinkError] = useState('');
  const [copied, setCopied] = useState(false);
  const [enrolledFaces, setEnrolledFaces] = useState([]);
  const [loadingFaces, setLoadingFaces] = useState(false);
  const [deleteStatus, setDeleteStatus] = useState({});

  // Load enrolled face list
  useEffect(() => { fetchFaces(); }, []);

  async function fetchFaces() {
    setLoadingFaces(true);
    try {
      const res = await listFaces();
      setEnrolledFaces(res.faces || []);
    } catch {
      // Silently skip if not yet available
    } finally {
      setLoadingFaces(false);
    }
  }

  const handleCapture = useCallback((frames) => {
    setCapturedFrames(frames);
  }, []);

  const handleReset = useCallback(() => {
    setCapturedFrames([]);
  }, []);

  function handleSuccess(name) {
    setCapturedFrames([]);
    fetchFaces();
  }

  function handleCancel() {
    setCapturedFrames([]);
  }

  async function handleGenerateLink() {
    setLinkLoading(true);
    setLinkError('');
    setEnrollLink('');
    try {
      const res = await createEnrollLink();
      // Build URL pointing to the React SPA, not the backend
      const frontendUrl = `${window.location.origin}/enroll/${res.token}`;
      setEnrollLink(frontendUrl);
      setShowLinkModal(true);
    } catch (err) {
      setLinkError(err.message || 'Failed to generate link');
      setShowLinkModal(true);
    } finally {
      setLinkLoading(false);
    }
  }

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(enrollLink);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback: select text
      const el = document.getElementById('enroll-link-input');
      if (el) { el.select(); document.execCommand('copy'); }
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }

  async function handleDelete(name) {
    setDeleteStatus(p => ({ ...p, [name]: 'loading' }));
    try {
      await deleteFace(name);
      setDeleteStatus(p => ({ ...p, [name]: 'done' }));
      setEnrolledFaces(prev => prev.filter(f => f !== name));
    } catch {
      setDeleteStatus(p => ({ ...p, [name]: 'error' }));
    }
  }

  return (
    <div style={pageStyles.page}>
      {/* Header */}
      <div style={pageStyles.header}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <ShieldCheck size={22} color="#22c55e" />
            <h1 style={pageStyles.title}>Face Enrollment</h1>
          </div>
          <p style={pageStyles.subtitle}>
            Register individuals for biometric access. Frames are processed on-device with liveness detection.
          </p>
        </div>
        <button
          onClick={handleGenerateLink}
          disabled={linkLoading}
          style={pageStyles.linkBtn}
        >
          <Link2 size={15} style={{ marginRight: 6 }} />
          {linkLoading ? 'Generating…' : 'Share Link'}
        </button>
      </div>

      {/* Main layout */}
      <div style={pageStyles.grid}>
        {/* Left: Camera */}
        <div style={pageStyles.card}>
          <p style={pageStyles.cardLabel}>Step 1 — Live Capture</p>
          <CapturePanel onCapture={handleCapture} onReset={handleReset} />
        </div>

        {/* Right: Form */}
        <div style={pageStyles.card}>
          <p style={pageStyles.cardLabel}>Step 2 — Identity Details</p>
          <IdentityForm
            capturedFrames={capturedFrames}
            enrolledNames={enrolledFaces}
            onSuccess={handleSuccess}
            onCancel={handleCancel}
          />
        </div>
      </div>

      {/* Enrolled faces list */}
      <div style={pageStyles.listCard}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#e2e8f0', fontWeight: 700, fontSize: 15 }}>
            <Users size={18} color="#3b82f6" />
            Enrolled Identities
            {enrolledFaces.length > 0 && (
              <span style={pageStyles.badge}>{enrolledFaces.length}</span>
            )}
          </span>
          <button onClick={fetchFaces} disabled={loadingFaces} style={pageStyles.refreshBtn}>
            <RefreshCw size={13} style={{ animation: loadingFaces ? 'spin 1s linear infinite' : 'none', marginRight: 4 }} />
            Refresh
          </button>
        </div>

        {enrolledFaces.length === 0 ? (
          <div style={pageStyles.emptyState}>
            No faces enrolled yet. Use the camera panel above or share an enrollment link.
          </div>
        ) : (
          <div style={pageStyles.faceGrid}>
            {enrolledFaces.map(name => (
              <div key={name} style={pageStyles.faceChip}>
                <div style={pageStyles.faceAvatar}>
                  {name.charAt(0).toUpperCase()}
                </div>
                <span style={{ flex: 1, fontSize: 13, color: '#e2e8f0', fontWeight: 500 }}>{name}</span>
                <button
                  onClick={() => handleDelete(name)}
                  disabled={deleteStatus[name] === 'loading'}
                  style={pageStyles.deleteBtn}
                  title="Remove enrollment"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Shareable Link Modal */}
      {showLinkModal && (
        <div style={pageStyles.modalBackdrop} onClick={() => setShowLinkModal(false)}>
          <div style={pageStyles.modal} onClick={e => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <h3 style={{ margin: 0, color: '#e2e8f0', fontSize: 16, fontWeight: 700 }}>Shareable Enrollment Link</h3>
              <button onClick={() => setShowLinkModal(false)} style={pageStyles.closeBtn}>
                <X size={16} />
              </button>
            </div>

            {linkError ? (
              <div style={{ color: '#fca5a5', fontSize: 13, padding: 12, background: 'rgba(239,68,68,0.1)', borderRadius: 8, border: '1px solid rgba(239,68,68,0.3)' }}>
                {linkError}
              </div>
            ) : (
              <>
                <p style={{ color: '#94a3b8', fontSize: 13, marginBottom: 12, lineHeight: 1.5 }}>
                  Share this link with the person to enroll. It expires in <strong style={{ color: '#e2e8f0' }}>1 hour</strong>.
                  Their upload will also be liveness-checked automatically.
                </p>
                <div style={pageStyles.linkRow}>
                  <input
                    id="enroll-link-input"
                    type="text"
                    readOnly
                    value={enrollLink}
                    style={pageStyles.linkInput}
                  />
                  <button onClick={handleCopy} style={pageStyles.copyBtn}>
                    {copied ? <Check size={15} /> : <Copy size={15} />}
                    {copied ? 'Copied!' : 'Copy'}
                  </button>
                </div>
                <p style={{ color: '#475569', fontSize: 11, marginTop: 8, textAlign: 'center' }}>
                  The link can only be used once and includes liveness detection.
                </p>
              </>
            )}
          </div>
        </div>
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

const pageStyles = {
  page: {
    padding: '24px',
    minHeight: '100vh',
    background: '#0a0f1e',
    display: 'flex',
    flexDirection: 'column',
    gap: 20,
    fontFamily: "'Inter', system-ui, sans-serif",
  },
  header: {
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: 16,
    flexWrap: 'wrap',
  },
  title: {
    margin: 0,
    fontSize: 22,
    fontWeight: 800,
    color: '#f1f5f9',
    letterSpacing: '-0.02em',
  },
  subtitle: {
    margin: '4px 0 0 32px',
    fontSize: 13,
    color: '#64748b',
    lineHeight: 1.5,
  },
  linkBtn: {
    display: 'inline-flex',
    alignItems: 'center',
    padding: '9px 18px',
    borderRadius: 10,
    border: '1px solid #334155',
    background: 'rgba(59,130,246,0.12)',
    color: '#93c5fd',
    fontSize: 14,
    fontWeight: 600,
    cursor: 'pointer',
    transition: 'background 0.2s',
    flexShrink: 0,
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
    gap: 20,
  },
  card: {
    display: 'flex',
    flexDirection: 'column',
    gap: 10,
  },
  cardLabel: {
    margin: 0,
    fontSize: 11,
    fontWeight: 700,
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
    color: '#475569',
  },
  listCard: {
    background: '#0f172a',
    borderRadius: 16,
    padding: 20,
    boxShadow: '0 4px 32px rgba(0,0,0,0.3)',
  },
  badge: {
    background: '#1e3a5f',
    color: '#93c5fd',
    borderRadius: 99,
    fontSize: 11,
    fontWeight: 700,
    padding: '2px 8px',
  },
  refreshBtn: {
    display: 'inline-flex',
    alignItems: 'center',
    padding: '5px 12px',
    borderRadius: 7,
    border: '1px solid #1e293b',
    background: 'transparent',
    color: '#64748b',
    fontSize: 12,
    cursor: 'pointer',
    fontWeight: 500,
  },
  emptyState: {
    color: '#475569',
    fontSize: 13,
    textAlign: 'center',
    padding: '28px 0',
    lineHeight: 1.6,
  },
  faceGrid: {
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
  },
  faceChip: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: '10px 12px',
    borderRadius: 10,
    background: '#1e293b',
    border: '1px solid #334155',
  },
  faceAvatar: {
    width: 32,
    height: 32,
    borderRadius: '50%',
    background: 'linear-gradient(135deg, #3b82f6, #6366f1)',
    color: '#fff',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontWeight: 800,
    fontSize: 14,
    flexShrink: 0,
  },
  deleteBtn: {
    padding: 6,
    borderRadius: 6,
    border: 'none',
    background: 'transparent',
    color: '#475569',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    transition: 'color 0.2s',
  },
  modalBackdrop: {
    position: 'fixed',
    inset: 0,
    background: 'rgba(0,0,0,0.7)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 999,
    backdropFilter: 'blur(4px)',
  },
  modal: {
    background: '#0f172a',
    border: '1px solid #1e293b',
    borderRadius: 16,
    padding: 24,
    width: '100%',
    maxWidth: 460,
    boxShadow: '0 20px 60px rgba(0,0,0,0.6)',
  },
  closeBtn: {
    background: 'transparent',
    border: 'none',
    color: '#64748b',
    cursor: 'pointer',
    padding: 4,
    display: 'flex',
    alignItems: 'center',
  },
  linkRow: {
    display: 'flex',
    gap: 8,
  },
  linkInput: {
    flex: 1,
    padding: '9px 12px',
    borderRadius: 8,
    border: '1px solid #334155',
    background: '#1e293b',
    color: '#93c5fd',
    fontSize: 12,
    fontFamily: 'monospace',
    outline: 'none',
  },
  copyBtn: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 5,
    padding: '9px 14px',
    borderRadius: 8,
    border: 'none',
    background: '#3b82f6',
    color: '#fff',
    fontSize: 13,
    fontWeight: 600,
    cursor: 'pointer',
    flexShrink: 0,
  },
};
