import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { ScanFace, ClipboardList, LogOut, Tv } from "lucide-react";
import { clearAuth, getStoredRole } from "../auth";

export default function AdminDashboardLayout() {
    const navigate = useNavigate();
    const role = getStoredRole() || "Admin";

    function handleLogout() {
        clearAuth();
        navigate("/auth", { replace: true });
    }

    const navClass = ({ isActive }) =>
        [
            "flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition",
            isActive
                ? "bg-slate-900 text-white"
                : "text-slate-700 hover:bg-slate-100 hover:text-slate-900",
        ].join(" ");

    return (
        <div className="grid min-h-screen grid-cols-[240px_1fr]">
            {/* ── Sidebar ─────────────────────────────────────── */}
            <aside className="flex flex-col border-r border-slate-200 bg-white p-5">
                {/* Brand */}
                <div className="mb-8 text-lg font-bold text-slate-900">Secure VU</div>

                {/* Nav */}
                <nav className="flex flex-col gap-1">
                    <NavLink to="face/enroll" className={navClass}>
                        <ScanFace size={18} />
                        Face Enrollment
                    </NavLink>

                    <NavLink to="face/logs" className={navClass}>
                        <ClipboardList size={18} />
                        Recognition Logs
                    </NavLink>

                    <NavLink to="live-feed" className={navClass}>
                        <Tv size={18} />
                        Live Feed
                    </NavLink>
                </nav>

                {/* Spacer + Logout */}
                <div className="mt-auto">
                    <div className="mb-4 h-px bg-slate-200" />
                    <div className="mb-3 px-3">
                        <div className="text-sm font-semibold capitalize text-slate-800">
                            {role.replace(/_/g, " ")}
                        </div>
                        <div className="text-xs text-slate-500">Admin Portal</div>
                    </div>
                    <button
                        onClick={handleLogout}
                        className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-red-600 transition hover:bg-red-50"
                    >
                        <LogOut size={16} />
                        Logout
                    </button>
                </div>
            </aside>

            {/* ── Main content ────────────────────────────────── */}
            <main className="p-6 lg:p-8 bg-slate-50 min-h-screen">
                <Outlet />
            </main>
        </div>
    );
}
