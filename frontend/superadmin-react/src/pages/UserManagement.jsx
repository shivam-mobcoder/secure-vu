import { useState, useEffect } from "react";
import { UserCog, ShieldCheck, ShieldAlert, Loader2 } from "lucide-react";
import { getStoredToken } from "../auth";

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
    const [updatingId, setUpdatingId] = useState(null);

    useEffect(() => {
        fetchMembers();
    }, []);

    async function fetchMembers() {
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
    }

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

            // Optimistic update
            setMembers(members.map(m =>
                m.id === memberId ? { ...m, permissions: newPerms } : m
            ));
        } catch (err) {
            alert(err.message);
        } finally {
            setUpdatingId(null);
        }
    }

    if (loading) {
        return (
            <div className="flex h-64 items-center justify-center">
                <Loader2 className="animate-spin text-slate-400" size={32} />
            </div>
        );
    }

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-slate-900">User Management</h1>
                <p className="text-slate-500">Manage access permissions for your members.</p>
            </div>

            {error && (
                <div className="rounded-lg bg-red-50 p-4 text-sm text-red-600">
                    {error}
                </div>
            )}

            <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
                <table className="w-full text-left text-sm">
                    <thead className="bg-slate-50 text-xs font-semibold uppercase tracking-wider text-slate-500">
                        <tr>
                            <th className="px-6 py-4">User</th>
                            <th className="px-6 py-4">Current Role</th>
                            <th className="px-6 py-4">Permissions</th>
                            <th className="px-6 py-4">Status</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                        {members.map((member) => (
                            <tr key={member.id} className="hover:bg-slate-50/50">
                                <td className="px-6 py-4">
                                    <div className="font-medium text-slate-900">{member.email}</div>
                                    <div className="text-xs text-slate-500">Member since {new Date(member.created_at || Date.now()).toLocaleDateString()}</div>
                                </td>
                                <td className="px-6 py-4">
                                    <span className="inline-flex items-center rounded-full bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700 capitalize">
                                        {member.role}
                                    </span>
                                </td>
                                <td className="px-6 py-4">
                                    <div className="flex items-center gap-3">
                                        <select
                                            disabled={updatingId === member.id}
                                            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
                                            value={JSON.stringify(member.permissions || [])}
                                            onChange={(e) => handlePermissionChange(member.id, JSON.parse(e.target.value))}
                                        >
                                            {PERMISSION_OPTIONS.map((opt) => (
                                                <option key={opt.label} value={JSON.stringify(opt.value)}>
                                                    {opt.label}
                                                </option>
                                            ))}
                                        </select>
                                        {updatingId === member.id && <Loader2 className="h-4 w-4 animate-spin text-blue-500" />}
                                    </div>
                                </td>
                                <td className="px-6 py-4">
                                    {member.is_active ? (
                                        <div className="flex items-center gap-1 text-emerald-600">
                                            <ShieldCheck size={16} />
                                            <span>Active</span>
                                        </div>
                                    ) : (
                                        <div className="flex items-center gap-1 text-slate-400">
                                            <ShieldAlert size={16} />
                                            <span>Inactive</span>
                                        </div>
                                    )}
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
                {members.length === 0 && (
                    <div className="py-12 text-center text-slate-500">
                        No members found for your client.
                    </div>
                )}
            </div>
        </div>
    );
}
