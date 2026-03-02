import { useState, useEffect, useCallback } from 'react';
import { Users, RefreshCw, Image, Calendar, Search, UserCheck, AlertTriangle, Download, Filter, Eye, ChevronLeft, ChevronRight, MoreHorizontal, Bell } from 'lucide-react';
import { fetchEnrolledFaces } from '../services/faceServices';

const REFRESH_INTERVAL_MS = 60_000; // refresh every 1m

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

    return (
        <div style={styles.page}>
            {/* Top Bar */}
            <div style={styles.topBar}>
                <div style={styles.globalSearch}>
                    <Search size={18} color="#94a3b8" />
                    <input type="text" placeholder="Search clients, subscriptions..." style={styles.globalSearchInput} />
                </div>
                <div style={styles.topActions}>
                    <button style={styles.notificationBtn}>
                        <Bell size={20} color="#64748b" />
                    </button>
                </div>
            </div>

            {/* Header Area */}
            <div style={styles.header}>
                <div style={styles.titleSection}>
                    <h1 style={styles.title}>Recognition Logs</h1>
                    <p style={styles.subtitle}>Audit trail of all biometric access attempts.</p>
                </div>
                <button style={styles.exportBtn}>
                    <Download size={16} style={{ marginRight: 8 }} />
                    Export CSV
                </button>
            </div>

            {/* Content Table Section */}
            <div style={styles.card}>
                {/* Search & Filter Row */}
                <div style={styles.toolbar}>
                    <div style={styles.searchContainer}>
                        <Search size={16} color="#94a3b8" />
                        <input
                            type="text"
                            placeholder="Search logs..."
                            value={search}
                            onChange={e => setSearch(e.target.value)}
                            style={styles.toolbarSearch}
                        />
                    </div>
                    <div style={styles.filterGroup}>
                        <div style={styles.selectWrapper}>
                            <select style={styles.select}>
                                <option>Status</option>
                            </select>
                        </div>
                        <div style={styles.selectWrapper}>
                            <select style={styles.select}>
                                <option>Role</option>
                            </select>
                        </div>
                        <button style={styles.filterIconButton}>
                            <Filter size={16} />
                        </button>
                    </div>
                </div>

                {/* Table */}
                <div style={styles.tableBoundary}>
                    <table style={styles.table}>
                        <thead>
                            <tr>
                                <th style={{ ...styles.th, width: '20%', textAlign: 'left' }}>Name</th>
                                <th style={{ ...styles.th, width: '15%', textAlign: 'center' }}>Persona</th>
                                <th style={{ ...styles.th, width: '20%', textAlign: 'center' }}>Date & Time</th>
                                <th style={{ ...styles.th, width: '15%', textAlign: 'left' }}>Match Score</th>
                                <th style={{ ...styles.th, width: '10%', textAlign: 'center' }}>Status</th>
                                <th style={{ ...styles.th, width: '15%', textAlign: 'center' }}>Device ID</th>
                                <th style={{ ...styles.th, width: '5%', textAlign: 'right' }}>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {loading && enrolled.length === 0 ? (
                                <tr>
                                    <td colSpan={7} style={styles.emptyTd}>
                                        <RefreshCw size={22} style={{ animation: 'spin 1s linear infinite', marginBottom: 12, color: '#6366f1' }} />
                                        <div style={{ color: '#64748b' }}>Syncing recognition logs...</div>
                                    </td>
                                </tr>
                            ) : filtered.length === 0 ? (
                                <tr>
                                    <td colSpan={7} style={styles.emptyTd}>
                                        <Users size={32} color="#cbd5e1" style={{ marginBottom: 12 }} />
                                        <div style={{ color: '#64748b' }}>{search ? 'No data matches your search' : 'No recognition data discovered'}</div>
                                    </td>
                                </tr>
                            ) : filtered.map((p) => {
                                // Deterministic hash for stable match score
                                const getHash = (str) => {
                                    let hash = 0;
                                    for (let i = 0; i < str.length; i++) {
                                        hash = str.charCodeAt(i) + ((hash << 5) - hash);
                                    }
                                    return Math.abs(hash);
                                };
                                const nameHash = getHash(p.name);
                                const score = p.image_count >= 5
                                    ? 90 + (nameHash % 10)
                                    : 12 + (nameHash % 8);

                                const isGranted = score > 50;
                                const isAlert = p.name.toLowerCase().includes('t-800');

                                return (
                                    <tr key={p.name} style={styles.tr}>
                                        <td style={{ ...styles.tdPrimary, textAlign: 'left' }}>{p.name}</td>
                                        <td style={{ ...styles.tdSecondary, textAlign: 'center' }}>
                                            {isAlert ? 'Blacklisted' : (p.role || 'Employee')}
                                        </td>
                                        <td style={{ ...styles.tdSecondary, textAlign: 'center' }}>{p.enrolled_at}</td>
                                        <td style={{ ...styles.tdScore, textAlign: 'left' }}>
                                            <div style={styles.scoreRowCenter}>
                                                <div style={styles.progressBar}>
                                                    <div style={{ ...styles.progressFill, width: `${score}%`, backgroundColor: isAlert ? '#1e293b' : (isGranted ? '#000' : '#cbd5e1') }} />
                                                </div>
                                                <span style={styles.scoreLabel}>{score}%</span>
                                            </div>
                                        </td>
                                        <td style={{ ...styles.tdStatus, textAlign: 'center' }}>
                                            <span style={{
                                                ...styles.badge,
                                                backgroundColor: isAlert ? '#000' : (isGranted ? '#f1f5f9' : '#ffffff'),
                                                color: isAlert ? '#fff' : '#000',
                                                border: isAlert ? 'none' : '1px solid #e2e8f0'
                                            }}>
                                                {isAlert ? 'ALERT' : (isGranted ? 'GRANTED' : 'DENIED')}
                                            </span>
                                        </td>
                                        <td style={{ ...styles.tdSecondary, textAlign: 'center' }}>{p.device || 'Lobby-01'}</td>
                                        <td style={{ ...styles.tdActions, textAlign: 'right' }}>
                                            <button style={styles.actionIcon}>
                                                <Eye size={16} />
                                            </button>
                                        </td>
                                    </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>

                {/* Pagination */}
                <div style={styles.pagination}>
                    <button style={styles.navBtn}>
                        <ChevronLeft size={18} /> Previous
                    </button>
                    <div style={styles.pageMarkers}>
                        <button style={{ ...styles.pageMarker, backgroundColor: '#f8fafc', borderColor: '#e2e8f0', fontWeight: 700 }}>1</button>
                        <button style={styles.pageMarker}>2</button>
                        <button style={styles.pageMarker}>3</button>
                        <span style={{ color: '#cbd5e1', padding: '0 4px' }}>...</span>
                    </div>
                    <button style={styles.navBtn}>
                        Next <ChevronRight size={18} />
                    </button>
                </div>
            </div>

            <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
    );
}

/* ── Styles ────────────────────────────────────────────────────── */
const styles = {
    page: {
        padding: '32px 48px',
        minHeight: '100vh',
        backgroundColor: '#ffffff',
        fontFamily: "'Inter', system-ui, sans-serif",
    },
    topBar: {
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        marginBottom: 40,
        padding: '0 4px', // Align with card content
    },
    globalSearch: {
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        padding: '0 16px',
        height: 44,
        width: 380,
        backgroundColor: '#ffffff',
        border: '1px solid #e2e8f0',
        borderRadius: 8,
    },
    globalSearchInput: {
        flex: 1,
        border: 'none',
        outline: 'none',
        fontSize: 14,
        color: '#1e293b',
    },
    notificationBtn: {
        background: 'none',
        border: 'none',
        cursor: 'pointer',
        padding: 4,
    },
    header: {
        display: 'flex',
        alignItems: 'flex-start',
        justifyContent: 'space-between',
        marginBottom: 32,
        padding: '0 4px', // Align with card content
    },
    titleSection: {
        display: 'flex',
        flexDirection: 'column',
        gap: 8,
    },
    title: {
        margin: 0,
        fontSize: 32,
        fontWeight: 700,
        color: '#111827',
        letterSpacing: '-0.025em',
    },
    subtitle: {
        margin: 0,
        fontSize: 15,
        color: '#6b7280',
    },
    exportBtn: {
        display: 'flex',
        alignItems: 'center',
        height: 38,
        padding: '0 16px',
        backgroundColor: '#ffffff',
        border: '1px solid #e5e7eb',
        borderRadius: 6,
        fontSize: 13,
        fontWeight: 600,
        color: '#374151',
        cursor: 'pointer',
    },
    card: {
        backgroundColor: '#ffffff',
        border: '1px solid #e5e7eb',
        borderRadius: 12,
        boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
        overflow: 'hidden',
    },
    toolbar: {
        padding: '20px 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        backgroundColor: '#ffffff',
        borderBottom: '1px solid #f3f4f6',
    },
    searchContainer: {
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '0 14px',
        height: 40,
        width: 280,
        backgroundColor: '#f9fafb',
        border: '1px solid #e5e7eb',
        borderRadius: 8,
    },
    toolbarSearch: {
        flex: 1,
        border: 'none',
        background: 'none',
        outline: 'none',
        fontSize: 14,
        color: '#1f2937',
    },
    filterGroup: {
        display: 'flex',
        alignItems: 'center',
        gap: 12,
    },
    selectWrapper: {
        height: 40,
        width: 130,
        position: 'relative',
    },
    select: {
        width: '100%',
        height: '100%',
        padding: '0 12px',
        backgroundColor: '#f9fafb',
        border: '1px solid #e5e7eb',
        borderRadius: 8,
        fontSize: 14,
        color: '#4b5563',
        appearance: 'none',
        outline: 'none',
    },
    filterIconButton: {
        width: 40,
        height: 40,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: '#ffffff',
        border: '1px solid #e5e7eb',
        borderRadius: 8,
        color: '#6b7280',
        cursor: 'pointer',
    },
    tableBoundary: {
        overflowX: 'auto',
    },
    table: {
        width: '100%',
        borderCollapse: 'collapse',
    },
    th: {
        backgroundColor: '#ffffff',
        padding: '16px 24px',
        fontSize: 13,
        fontWeight: 800,
        color: '#111827',
        borderBottom: '1px solid #f3f4f6',
    },
    tr: {
        borderBottom: '1px solid #f3f4f6',
    },
    tdPrimary: {
        padding: '16px 24px',
        fontSize: 14,
        fontWeight: 700,
        color: '#000000',
    },
    tdSecondary: {
        padding: '16px 24px',
        fontSize: 14,
        color: '#6b7280',
    },
    tdScore: {
        padding: '16px 24px',
    },
    scoreRowCenter: {
        display: 'inline-flex',
        alignItems: 'center',
        gap: 12,
        marginRight: 12,
    },
    progressBar: {
        width: 80,
        height: 6,
        backgroundColor: '#f3f4f6',
        borderRadius: 3,
        overflow: 'hidden',
    },
    progressFill: {
        height: '100%',
        borderRadius: 3,
    },
    scoreLabel: {
        fontSize: 13,
        color: '#4b5563',
        fontWeight: 500,
    },
    tdStatus: {
        padding: '16px 24px',
    },
    badge: {
        display: 'inline-flex',
        alignItems: 'center',
        padding: '4px 12px',
        borderRadius: 99,
        fontSize: 11,
        fontWeight: 700,
        letterSpacing: '0.02em',
    },
    tdActions: {
        padding: '16px 24px',
    },
    actionIcon: {
        background: 'none',
        border: 'none',
        cursor: 'pointer',
        padding: 4,
        color: '#9ca3af',
    },
    pagination: {
        padding: '24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 24,
        backgroundColor: '#ffffff',
    },
    navBtn: {
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        padding: '0 8px',
        background: 'none',
        border: 'none',
        fontSize: 14,
        fontWeight: 600,
        color: '#374151',
        cursor: 'pointer',
    },
    pageMarkers: {
        display: 'flex',
        alignItems: 'center',
        gap: 6,
    },
    pageMarker: {
        width: 36,
        height: 36,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: '#ffffff',
        border: '1px solid #e5e7eb',
        borderRadius: 6,
        fontSize: 14,
        color: '#374151',
        cursor: 'pointer',
    },
    emptyTd: {
        padding: '80px 0',
        textAlign: 'center',
    }
};
