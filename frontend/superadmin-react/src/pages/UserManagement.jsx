import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
    UserPlus,
    Search,
    Filter,
    Settings,
    UserX,
    ChevronLeft,
    ChevronRight,
    Loader2,
    Bell
} from "lucide-react";
import { getStoredToken } from "../auth";
import "../styles/usermanagement.css";

const PERMISSION_OPTIONS = [
    { label: "Enrollment Only", value: ["face_enroll"] },
    { label: "Logs Only", value: ["recognition_logs"] },
    { label: "Feed Only", value: ["live_feed"] },
    { label: "Logs & Feed", value: ["recognition_logs", "live_feed"] },
    { label: "Full Access", value: ["face_enroll", "recognition_logs", "live_feed"] },
    { label: "None", value: [] },
];

export default function UserManagement() {
    const [members, setMembers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [search, setSearch] = useState("");
    const [updatingId, setUpdatingId] = useState(null);
    const navigate = useNavigate();

    const fetchMembers = useCallback(async () => {
        try {
            const res = await fetch("/api/admin/members", {
                headers: {
                    Authorization: `Bearer ${getStoredToken()}`,
                    Accept: "application/json",
                },
            });
            if (!res.ok) throw new Error("Failed to fetch members");
            const data = await res.json();
            setMembers(data.members || []);
        } catch (err) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchMembers();
    }, [fetchMembers]);

    async function handlePermissionChange(memberId, newPerms) {
        setUpdatingId(memberId);
        try {
            const res = await fetch(`/api/admin/members/${memberId}/permissions`, {
                method: "PATCH",
                headers: {
                    Authorization: `Bearer ${getStoredToken()}`,
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ permissions: newPerms }),
            });
            if (!res.ok) throw new Error("Update failed");

            setMembers(members.map(m =>
                m.id === memberId ? { ...m, permissions: newPerms } : m
            ));
        } catch (err) {
            alert(err.message);
        } finally {
            setUpdatingId(null);
        }
    }

    const filtered = members.filter(m =>
        m.email.toLowerCase().includes(search.toLowerCase())
    );

    return (
        <div className="um-page">
            {/* Top Bar */}
            <div className="um-top-bar">
                <div className="um-global-search">
                    <Search size={18} color="#94a3b8" />
                    <input type="text" placeholder="Search clients, subscriptions..." className="um-global-search-input" />
                </div>
                <div className="um-top-actions">
                    <button className="um-notification-btn">
                        <Bell size={20} color="#64748b" />
                    </button>
                </div>
            </div>

            {/* Header Area */}
            <div className="um-header">
                <div className="um-title-section">
                    <h1 className="um-title">User Management</h1>
                    <p className="um-subtitle">Manage identities, roles, and access permissions.</p>
                </div>
                <div style={{ display: 'flex', gap: 12 }}>
                    <button className="um-add-user-btn">
                        <UserPlus size={16} />
                        Add User
                    </button>
                    <button className="um-filter-btn" onClick={() => navigate("/admin/dashboard/system-settings")}>
                        <Settings size={16} />
                        Settings
                    </button>
                </div>
            </div>

            {/* Content Table Section */}
            <div className="um-card">
                {/* Search & Filter Row */}
                <div className="um-toolbar">
                    <div className="um-search-container">
                        <Search size={16} color="#94a3b8" />
                        <input
                            type="text"
                            placeholder="Search users by name or email..."
                            value={search}
                            onChange={e => setSearch(e.target.value)}
                            className="um-toolbar-search"
                        />
                    </div>
                    <button className="um-filter-btn">
                        <Filter size={16} />
                        Filter
                    </button>
                </div>

                {/* Table */}
                <div className="um-table-boundary">
                    <table className="um-table">
                        <thead>
                            <tr>
                                <th className="um-th" style={{ width: '25%' }}>User</th>
                                <th className="um-th" style={{ width: '10%' }}>Role</th>
                                <th className="um-th" style={{ width: '15%' }}>Organization</th>
                                <th className="um-th" style={{ width: '15%' }}>Access</th>
                                <th className="um-th" style={{ width: '10%' }}>Status</th>
                                <th className="um-th" style={{ width: '15%' }}>Face Enrolled</th>
                                <th className="um-th" style={{ width: '10%', textAlign: 'right' }}>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {loading ? (
                                <tr>
                                    <td colSpan={7} className="um-empty-td">
                                        <Loader2 size={24} className="animate-spin" style={{ color: '#6366f1', marginBottom: 12 }} />
                                        <div style={{ color: '#64748b' }}>Fetching user directory...</div>
                                    </td>
                                </tr>
                            ) : filtered.length === 0 ? (
                                <tr>
                                    <td colSpan={7} className="um-empty-td">
                                        <div style={{ color: '#64748b' }}>{search ? 'No users matching your search' : 'No users found'}</div>
                                    </td>
                                </tr>
                            ) : filtered.map((member) => (
                                <tr key={member.id} className="um-tr">
                                    <td className="um-td-user">
                                        <div className="um-user-cell">
                                            <div className="um-avatar">
                                                {member.email.charAt(0).toUpperCase()}
                                            </div>
                                            <div className="um-user-info">
                                                <div className="um-user-name">{member.email.split('@')[0]}</div>
                                                <div className="um-user-email">{member.email}</div>
                                            </div>
                                        </div>
                                    </td>
                                    <td className="um-td-secondary">
                                        <span className="um-badge" style={{
                                            backgroundColor: member.role === 'admin' ? '#f1f5f9' : '#ffffff',
                                            border: '1px solid #e2e8f0',
                                            textTransform: 'capitalize'
                                        }}>
                                            {member.role || 'Member'}
                                        </span>
                                    </td>
                                    <td className="um-td-secondary">
                                        {member.organization || "Pescadero State"}
                                    </td>
                                    <td className="um-td-secondary">
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                            <select
                                                disabled={updatingId === member.id}
                                                className="um-inline-select"
                                                value={JSON.stringify(member.permissions || [])}
                                                onChange={(e) => handlePermissionChange(member.id, JSON.parse(e.target.value))}
                                            >
                                                {PERMISSION_OPTIONS.map((opt) => (
                                                    <option key={opt.label} value={JSON.stringify(opt.value)}>
                                                        {opt.label}
                                                    </option>
                                                ))}
                                            </select>
                                            {updatingId === member.id && <Loader2 size={12} className="animate-spin" style={{ color: '#3b82f6' }} />}
                                        </div>
                                    </td>
                                    <td className="um-td-secondary">
                                        <div className="um-status-row">
                                            <div className="um-status-dot" style={{ backgroundColor: member.is_active ? '#000000' : '#94a3b8' }} />
                                            <span>{member.is_active ? 'Active' : 'Inactive'}</span>
                                        </div>
                                    </td>
                                    <td className="um-td-secondary">
                                        <span className="um-badge" style={{
                                            backgroundColor: member.face_enrolled ? '#fef3c7' : '#f1f5f9',
                                            color: '#000',
                                            fontWeight: 600
                                        }}>
                                            {member.face_enrolled ? 'Enrolled' : 'Pending'}
                                        </span>
                                    </td>
                                    <td className="um-td-actions">
                                        <div className="um-action-group">
                                            <button className="um-icon-btn"><Settings size={16} /></button>
                                            <button className="um-icon-btn"><UserX size={16} /></button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>

                {/* Pagination */}
                <div className="um-pagination">
                    <button className="um-nav-btn">
                        <ChevronLeft size={18} /> Previous
                    </button>
                    <div className="um-page-markers">
                        <button className="um-page-marker" style={{ backgroundColor: '#f8fafc', borderColor: '#e2e8f0', fontWeight: 700 }}>1</button>
                        <button className="um-page-marker">2</button>
                        <button className="um-page-marker">3</button>
                        <span style={{ color: '#cbd5e1', padding: '0 4px' }}>...</span>
                    </div>
                    <button className="um-nav-btn">
                        Next <ChevronRight size={18} />
                    </button>
                </div>
            </div>
        </div>
    );
}
