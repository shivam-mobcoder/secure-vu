import { useState, useCallback, useEffect } from 'react';
import { Link2, Copy, Check, X, Users, Trash2, RefreshCw, ShieldCheck, Shield } from 'lucide-react';
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
          <h1 style={pageStyles.title}>New Face Enrollment</h1>
          <p style={pageStyles.subtitle}>
            Register a new identity into the biometric database.
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
          <div style={pageStyles.cardHeader}>
            <h2 style={pageStyles.cardTitle}>Live Capture</h2>
            <p style={pageStyles.cardSubtitle}>Position face within the frame and ensure good lighting.</p>
          </div>
          <div style={pageStyles.cardContent}>
            <CapturePanel onCapture={handleCapture} onReset={handleReset} />
          </div>
        </div>

        {/* Right: Form */}
        <div style={pageStyles.card}>
          <div style={pageStyles.cardHeader}>
            <h2 style={pageStyles.cardTitle}>Identity Details</h2>
            <p style={pageStyles.cardSubtitle}>Associate biometric data with a user profile.</p>
          </div>
          <div style={pageStyles.cardContent}>
            <IdentityForm
              capturedFrames={capturedFrames}
              enrolledNames={enrolledFaces}
              onSuccess={handleSuccess}
              onCancel={handleCancel}
            />
          </div>
        </div>
      </div>

      {/* Privacy Banner */}
      <div style={pageStyles.privacyBanner}>
        <div style={pageStyles.privacyIcon}>
          <Shield size={18} color="#64748b" />
        </div>
        <div>
          <h4 style={pageStyles.privacyTitle}>Biometric Privacy & Security</h4>
          <p style={pageStyles.privacyText}>
            Face templates are irreversibly hashed and encrypted using AES-256 before storage. Raw images are not retained after enrollment process is complete.
          </p>
        </div>
      </div>

      {/* Enrolled faces list */}
      <div style={pageStyles.listCard}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#1e293b', fontWeight: 700, fontSize: 15 }}>
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
                <span style={{ flex: 1, fontSize: 13, color: '#1e293b', fontWeight: 500 }}>{name}</span>
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
              <h3 style={{ margin: 0, color: '#1e293b', fontSize: 16, fontWeight: 700 }}>Shareable Enrollment Link</h3>
              <button onClick={() => setShowLinkModal(false)} style={pageStyles.closeBtn}>
                <X size={16} />
              </button>
            </div>

            {linkError ? (
              <div style={{ color: '#ef4444', fontSize: 13, padding: 12, background: 'rgba(239,68,68,0.05)', borderRadius: 8, border: '1px solid rgba(239,68,68,0.2)' }}>
                {linkError}
              </div>
            ) : (
              <>
                <p style={{ color: '#64748b', fontSize: 13, marginBottom: 12, lineHeight: 1.5 }}>
                  Share this link with the person to enroll. It expires in <strong style={{ color: '#1e293b' }}>1 hour</strong>.
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
    padding: '32px',
    minHeight: '100vh',
    background: '#f8fafc',
    display: 'flex',
    flexDirection: 'column',
    gap: 32,
    fontFamily: "'Inter', system-ui, sans-serif",
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 16,
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
  linkBtn: {
    display: 'inline-flex',
    alignItems: 'center',
    padding: '10px 20px',
    borderRadius: 8,
    border: '1px solid #e2e8f0',
    background: '#ffffff',
    color: '#1e293b',
    fontSize: 14,
    fontWeight: 600,
    cursor: 'pointer',
    boxShadow: '0 1px 2px rgba(0,0,0,0.05)',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))',
    gap: 32,
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
  privacyBanner: {
    display: 'flex',
    alignItems: 'flex-start',
    gap: 16,
    background: '#f1f5f9',
    padding: '20px',
    borderRadius: 12,
    border: '1px solid #e2e8f0',
  },
  privacyIcon: {
    width: 40,
    height: 40,
    borderRadius: 8,
    background: '#ffffff',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    border: '1px solid #e2e8f0',
    flexShrink: 0,
  },
  privacyTitle: {
    margin: 0,
    fontSize: 14,
    fontWeight: 700,
    color: '#1e293b',
  },
  privacyText: {
    margin: '4px 0 0',
    fontSize: 12,
    color: '#64748b',
    lineHeight: 1.5,
  },
  listCard: {
    background: '#ffffff',
    borderRadius: 12,
    padding: '24px',
    border: '1px solid #e2e8f0',
    boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
  },
  badge: {
    background: '#eff6ff',
    color: '#3b82f6',
    borderRadius: 99,
    fontSize: 11,
    fontWeight: 700,
    padding: '2px 8px',
  },
  refreshBtn: {
    display: 'inline-flex',
    alignItems: 'center',
    padding: '6px 14px',
    borderRadius: 8,
    border: '1px solid #e2e8f0',
    background: 'transparent',
    color: '#64748b',
    fontSize: 12,
    cursor: 'pointer',
    fontWeight: 600,
  },
  emptyState: {
    color: '#94a3b8',
    fontSize: 14,
    textAlign: 'center',
    padding: '40px 0',
  },
  faceGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
    gap: 12,
  },
  faceChip: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    padding: '12px',
    borderRadius: 10,
    background: '#f8fafc',
    border: '1px solid #f1f5f9',
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
    padding: 8,
    borderRadius: 8,
    border: 'none',
    background: 'transparent',
    color: '#94a3b8',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    transition: 'all 0.2s',
    '&:hover': {
      color: '#ef4444',
      background: '#fee2e2',
    }
  },
  modalBackdrop: {
    position: 'fixed',
    inset: 0,
    background: 'rgba(15, 23, 42, 0.7)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 999,
    backdropFilter: 'blur(8px)',
  },
  modal: {
    background: '#ffffff',
    border: '1px solid #e2e8f0',
    borderRadius: 16,
    padding: 32,
    width: '100%',
    maxWidth: 480,
    boxShadow: '0 25px 50px -12px rgba(0,0,0,0.25)',
  },
  closeBtn: {
    background: 'transparent',
    border: 'none',
    color: '#94a3b8',
    cursor: 'pointer',
    padding: 4,
    display: 'flex',
    alignItems: 'center',
  },
  linkRow: {
    display: 'flex',
    gap: 8,
    background: '#f8fafc',
    padding: '4px',
    borderRadius: 10,
    border: '1px solid #e2e8f0',
  },
  linkInput: {
    flex: 1,
    padding: '10px 14px',
    borderRadius: 8,
    border: 'none',
    background: 'transparent',
    color: '#3b82f6',
    fontSize: 13,
    fontFamily: 'monospace',
    outline: 'none',
  },
  copyBtn: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    padding: '10px 18px',
    borderRadius: 8,
    border: 'none',
    background: '#0f172a',
    color: '#fff',
    fontSize: 13,
    fontWeight: 600,
    cursor: 'pointer',
  },
};
