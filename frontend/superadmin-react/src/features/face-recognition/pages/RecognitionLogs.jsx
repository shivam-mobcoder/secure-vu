import { useState, useEffect, useCallback } from 'react';
import { Users, RefreshCw, Image, Calendar, Search, UserCheck, AlertTriangle } from 'lucide-react';
import { fetchEnrolledFaces } from '../services/faceServices';

const REFRESH_INTERVAL_MS = 30_000; // refresh every 30s

/* ── Main Component ───────────────────────────────────────────── */
export default function RecognitionLogs() {
    const [enrolled, setEnrolled] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [search, setSearch] = useState('');

    const loadData = useCallback(async () => {
        try {
            const data = await fetchEnrolledFaces();
            setEnrolled(data.enrolled || []);
            setError(null);
        } catch (e) {
            setError(e.message);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        loadData();
        const iv = setInterval(loadData, REFRESH_INTERVAL_MS);
        return () => clearInterval(iv);
    }, [loadData]);

    const filtered = enrolled.filter(p =>
        p.name.toLowerCase().includes(search.toLowerCase())
    );

    const totalImages = enrolled.reduce((sum, p) => sum + (p.image_count || 0), 0);

    return (
        <div style={styles.page}>
            {/* Header */}
            <div style={styles.header}>
                <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <Users size={22} color="#6366f1" />
                        <h1 style={styles.title}>Enrolled Faces</h1>
                    </div>
                    <p style={styles.subtitle}>
                        People registered in the face recognition database
                    </p>
                </div>
                <button onClick={loadData} disabled={loading} style={styles.refreshBtn}>
                    <RefreshCw size={14} style={{
                        marginRight: 6,
                        animation: loading ? 'spin 1s linear infinite' : 'none'
                    }} />
                    Refresh
                </button>
            </div>

            {/* Stats Cards */}
            <div style={styles.statsRow}>
                <div style={styles.statCard}>
                    <UserCheck size={18} color="#22c55e" />
                    <div>
                        <div style={styles.statValue}>{enrolled.length}</div>
                        <div style={styles.statLabel}>Enrolled People</div>
                    </div>
                </div>
                <div style={styles.statCard}>
                    <Image size={18} color="#3b82f6" />
                    <div>
                        <div style={styles.statValue}>{totalImages}</div>
                        <div style={styles.statLabel}>Total Images</div>
                    </div>
                </div>
            </div>

            {/* Search */}
            <div style={styles.searchBox}>
                <Search size={15} color="#64748b" style={{ flexShrink: 0 }} />
                <input
                    type="text"
                    placeholder="Search enrolled people..."
                    value={search}
                    onChange={e => setSearch(e.target.value)}
                    style={styles.searchInput}
                />
            </div>

            {/* Error */}
            {error && (
                <div style={styles.errorMsg}>
                    <AlertTriangle size={14} style={{ flexShrink: 0 }} />
                    {error}
                </div>
            )}

            {/* Table */}
            <div style={styles.tableWrap}>
                <table style={styles.table}>
                    <thead>
                        <tr>
                            <th style={styles.th}>#</th>
                            <th style={styles.th}>Name</th>
                            <th style={styles.th}>Images</th>
                            <th style={styles.th}>Enrolled On</th>
                            <th style={styles.th}>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {loading && enrolled.length === 0 ? (
                            <tr>
                                <td colSpan={5} style={styles.emptyTd}>
                                    <RefreshCw size={18} style={{ animation: 'spin 1s linear infinite', marginBottom: 8 }} />
                                    <div>Loading enrolled faces...</div>
                                </td>
                            </tr>
                        ) : filtered.length === 0 ? (
                            <tr>
                                <td colSpan={5} style={styles.emptyTd}>
                                    <Users size={24} color="#334155" style={{ marginBottom: 8 }} />
                                    <div>{search ? 'No matches found' : 'No faces enrolled yet'}</div>
                                    <div style={{ fontSize: 12, color: '#475569', marginTop: 4 }}>
                                        {search ? 'Try a different search' : 'Use the Face Enrollment page to register people'}
                                    </div>
                                </td>
                            </tr>
                        ) : filtered.map((person, i) => (
                            <tr key={person.name} style={styles.tr}>
                                <td style={styles.td}>{i + 1}</td>
                                <td style={styles.tdName}>
                                    <div style={styles.avatar}>
                                        {person.name.charAt(0).toUpperCase()}
                                    </div>
                                    <span style={{ fontWeight: 600, color: '#e2e8f0' }}>
                                        {person.name}
                                    </span>
                                </td>
                                <td style={styles.td}>
                                    <span style={styles.imageBadge}>
                                        <Image size={12} />
                                        {person.image_count}
                                    </span>
                                </td>
                                <td style={styles.td}>
                                    <span style={{ color: '#94a3b8', fontSize: 13 }}>
                                        <Calendar size={12} style={{ marginRight: 4, verticalAlign: -1 }} />
                                        {person.enrolled_at}
                                    </span>
                                </td>
                                <td style={styles.td}>
                                    <span style={{
                                        ...styles.statusBadge,
                                        background: person.image_count >= 5
                                            ? 'rgba(34,197,94,0.12)'
                                            : 'rgba(245,158,11,0.12)',
                                        color: person.image_count >= 5 ? '#4ade80' : '#fbbf24',
                                        borderColor: person.image_count >= 5
                                            ? 'rgba(34,197,94,0.3)'
                                            : 'rgba(245,158,11,0.3)',
                                    }}>
                                        {person.image_count >= 5 ? '● Active' : '◐ Low Data'}
                                    </span>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
    );
}

/* ── Styles ────────────────────────────────────────────────────── */
const styles = {
    page: {
        padding: 24,
        minHeight: '100vh',
        background: '#0a0f1e',
        display: 'flex',
        flexDirection: 'column',
        gap: 18,
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
    refreshBtn: {
        display: 'inline-flex',
        alignItems: 'center',
        padding: '8px 16px',
        borderRadius: 10,
        border: '1px solid #1e293b',
        background: 'rgba(99,102,241,0.08)',
        color: '#a5b4fc',
        fontSize: 13,
        fontWeight: 600,
        cursor: 'pointer',
    },
    statsRow: {
        display: 'flex',
        gap: 14,
        flexWrap: 'wrap',
    },
    statCard: {
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '14px 20px',
        borderRadius: 12,
        background: '#0f172a',
        border: '1px solid #1e293b',
        minWidth: 160,
    },
    statValue: {
        fontSize: 22,
        fontWeight: 800,
        color: '#e2e8f0',
        lineHeight: 1,
    },
    statLabel: {
        fontSize: 11,
        color: '#64748b',
        fontWeight: 500,
        marginTop: 2,
    },
    searchBox: {
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '10px 14px',
        borderRadius: 10,
        background: '#0f172a',
        border: '1px solid #1e293b',
    },
    searchInput: {
        flex: 1,
        background: 'transparent',
        border: 'none',
        outline: 'none',
        color: '#e2e8f0',
        fontSize: 14,
    },
    errorMsg: {
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '10px 14px',
        borderRadius: 10,
        background: 'rgba(239,68,68,0.08)',
        border: '1px solid rgba(239,68,68,0.2)',
        color: '#fca5a5',
        fontSize: 13,
    },
    tableWrap: {
        borderRadius: 14,
        overflow: 'hidden',
        border: '1px solid #1e293b',
        background: '#0f172a',
    },
    table: {
        width: '100%',
        borderCollapse: 'collapse',
        fontSize: 14,
    },
    th: {
        textAlign: 'left',
        padding: '12px 16px',
        color: '#64748b',
        fontWeight: 600,
        fontSize: 11,
        textTransform: 'uppercase',
        letterSpacing: '0.05em',
        borderBottom: '1px solid #1e293b',
        background: 'rgba(15,23,42,0.6)',
    },
    tr: {
        borderBottom: '1px solid #1e293b22',
        transition: 'background 0.15s',
    },
    td: {
        padding: '12px 16px',
        color: '#94a3b8',
        verticalAlign: 'middle',
    },
    tdName: {
        padding: '12px 16px',
        display: 'flex',
        alignItems: 'center',
        gap: 10,
    },
    avatar: {
        width: 32,
        height: 32,
        borderRadius: '50%',
        background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
        color: '#fff',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontWeight: 800,
        fontSize: 14,
        flexShrink: 0,
    },
    imageBadge: {
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        padding: '3px 8px',
        borderRadius: 6,
        background: 'rgba(59,130,246,0.1)',
        color: '#93c5fd',
        fontSize: 12,
        fontWeight: 600,
    },
    statusBadge: {
        display: 'inline-block',
        padding: '3px 10px',
        borderRadius: 6,
        fontSize: 12,
        fontWeight: 600,
        border: '1px solid',
    },
    emptyTd: {
        padding: '40px 16px',
        textAlign: 'center',
        color: '#64748b',
        fontSize: 14,
    },
};
