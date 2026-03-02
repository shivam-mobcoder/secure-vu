import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
    ScanFace,
    ClipboardList,
    LogOut,
    Tv,
    Users,
    Settings,
    ChevronDown,
    ChevronUp,
    Shield
} from "lucide-react";
import { clearAuth, getStoredRole, getStoredPermissions } from "../auth";

export default function AdminDashboardLayout() {
    const navigate = useNavigate();
    const [isFaceRecOpen, setIsFaceRecOpen] = useState(true);
    const role = (getStoredRole() || "admin").toLowerCase();
    const isAdmin = role === "admin" || role === "super_admin";
    const perms = getStoredPermissions();

    // Profile footer info
    const user = {
        name: "admin@internal.com",
        roleName: isAdmin ? "Administrator" : "Member",
        initials: "A"
    };

    function handleLogout() {
        clearAuth();
        navigate("/auth", { replace: true });
    }

    const navClass = ({ isActive }) =>
        [
            "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-200",
            isActive
                ? "bg-slate-100 text-slate-900"
                : "text-slate-600 hover:bg-slate-50 hover:text-slate-900",
        ].join(" ");

    const subNavClass = ({ isActive }) =>
        [
            "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-200 ml-6",
            isActive
                ? "bg-slate-100 text-slate-900"
                : "text-slate-500 hover:bg-slate-50 hover:text-slate-900",
        ].join(" ");

    const hasPerm = (p) => isAdmin || perms.includes(p);

    return (
        <div className="grid min-h-screen grid-cols-[240px_1fr]">
            {/* ── Sidebar ─────────────────────────────────────── */}
            <aside className="flex flex-col border-r border-slate-200 bg-white p-5 sticky top-0 h-screen">
                {/* Brand */}
                <div className="mb-8 text-lg font-bold text-slate-900">Secure VU</div>

                {/* Nav */}
                <nav className="flex flex-col gap-1">
                    {/* Consolidated Face Recognition Dropdown */}
                    <div>
                        <button
                            onClick={() => setIsFaceRecOpen(!isFaceRecOpen)}
                            className="flex w-full items-center justify-between rounded-lg px-3 py-2 text-sm font-semibold text-slate-900 transition hover:bg-slate-50"
                        >
                            <span>Face Recognition</span>
                            {isFaceRecOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                        </button>

                        {isFaceRecOpen && (
                            <div className="mt-1 flex flex-col gap-1">
                                {hasPerm("face_enroll") && (
                                    <NavLink to="face/enroll" className={subNavClass}>
                                        <ScanFace size={18} />
                                        Face Enrollment
                                    </NavLink>
                                )}
                                {hasPerm("recognition_logs") && (
                                    <NavLink to="face/logs" className={subNavClass}>
                                        <ClipboardList size={18} />
                                        Recognition Logs
                                    </NavLink>
                                )}
                                {hasPerm("live_feed") && (
                                    <NavLink to="live-feed" className={subNavClass}>
                                        <Tv size={18} />
                                        Live Feed
                                    </NavLink>
                                )}

                                {isAdmin && (
                                    <>
                                        <NavLink to="users" className={subNavClass}>
                                            <Users size={18} />
                                            Users
                                        </NavLink>
                                        <NavLink to="system-settings" className={subNavClass}>
                                            <Settings size={18} />
                                            System Settings
                                        </NavLink>
                                    </>
                                )}
                            </div>
                        )}
                    </div>
                </nav>

                {/* Profile Footer */}
                <div className="mt-auto pt-6 border-t border-slate-100">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-100 text-sm font-bold text-slate-600">
                                {user.initials}
                            </div>
                            <div className="flex flex-col">
                                <span className="text-sm font-bold text-slate-900 leading-tight">{user.name}</span>
                                <span className="text-xs text-slate-500">{user.roleName}</span>
                            </div>
                        </div>
                        <button
                            onClick={handleLogout}
                            className="p-2 text-slate-400 hover:text-red-600 transition"
                            title="Sign out"
                        >
                            <LogOut size={18} />
                        </button>
                    </div>
                </div>
            </aside>

            {/* ── Main content ────────────────────────────────── */}
            <main className="p-6 lg:p-8 bg-slate-50 min-h-screen">
                <Outlet />
            </main>
        </div>
    );
}
