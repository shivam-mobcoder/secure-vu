import { NavLink, Outlet, useLocation, useNavigate, Navigate } from "react-router-dom";
import {
  Bell,
  Users,
  CreditCard,
  DollarSign,
  Settings as SettingIcon,
  LogOut,
} from "lucide-react";
import { getStoredToken, clearAuth, getStoredRole } from "../auth";

export default function AdminLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const token = getStoredToken();
  const role = getStoredRole() || "Super Admin";

  // Guard: redirect to login if no token
  if (!token) {
    return <Navigate to="/auth" replace />;
  }

  const initials = "SA";

  function handleLogout() {
    clearAuth();
    navigate("/auth", { replace: true });
  }

  const headerByPath = [
    {
      match: (path) => path.includes("client-management"),
      title: "Client Management",
      subtitle: "Manage and monitor all client accounts and subscriptions",
    },
    {
      match: (path) => path.includes("client/new"),
      title: "Add New Client",
      subtitle: "Create a new client account with subscription details",
    },
    {
      match: (path) => path.includes("client/"),
      title: "Client Detail View",
      subtitle: "Complete client information and subscription details",
    },
    {
      match: (path) => path.includes("subscription-management"),
      title: "Subscription Management",
      subtitle: "Create and manage subscription plans for your clients",
    },
    {
      match: (path) => path.includes("billing-overview"),
      title: "Billing & Status Overview",
      subtitle: "Track billing performance and payment trends",
    },
    {
      match: (path) => path.includes("settings"),
      title: "Settings",
      subtitle: "Manage global preferences and platform configuration",
    },
  ];

  const currentHeader =
    headerByPath.find(({ match }) => match(location.pathname)) || headerByPath[0];

  const navClass = ({ isActive }) =>
    [
      "flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition",
      isActive
        ? "bg-slate-900 text-white"
        : "text-slate-700 hover:bg-slate-100 hover:text-slate-900",
    ].join(" ");

  return (
    <div className="grid min-h-screen grid-cols-[240px_1fr]">
      <aside className="flex flex-col border-r border-slate-200 bg-white p-5">
        <div className="mb-8 text-lg font-bold text-slate-900">Secure VU</div>

        <nav className="flex flex-col gap-1">
          <NavLink
            to="client-management"
            end
            className={navClass}
          >
            <Users size={18} />
            Client Management
          </NavLink>

          <NavLink
            to="subscription-management"
            className={navClass}
          >
            <CreditCard size={16} />
            Subscription Management
          </NavLink>

          <NavLink
            to="billing-overview"
            className={navClass}
          >
            <DollarSign size={16} />
            Billing & Overview
          </NavLink>

          <div className="my-3 h-px bg-slate-200" />

          <NavLink
            to="settings"
            className={navClass}
          >
            <SettingIcon size={16} />
            Settings
          </NavLink>
        </nav>

        {/* Spacer + Logout */}
        <div className="mt-auto">
          <div className="mb-4 h-px bg-slate-200" />
          <div className="mb-3 px-3">
            <div className="text-sm font-semibold capitalize text-slate-800">
              {role.replace(/_/g, " ")}
            </div>
            <div className="text-xs text-slate-500">Super Admin Portal</div>
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

      <main className="p-6 lg:p-8">
        <div className="mb-6 flex items-start justify-between gap-4">
          <div className="min-w-0">
            <h2 className="text-2xl font-bold tracking-tight text-slate-900">{currentHeader.title}</h2>
            <p className="mt-1 text-sm text-slate-500">{currentHeader.subtitle}</p>
          </div>

          <div className="flex items-center gap-4">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600">
              <Bell size={18} />
            </div>

            <div className="h-7 w-px bg-slate-200" />

            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center overflow-hidden rounded-full bg-slate-900 text-sm font-semibold text-white">
                {initials}
              </div>

              <div className="flex flex-col">
                <div className="text-sm font-semibold text-slate-900">{role.replace(/_/g, " ")}</div>
                <div className="text-xs text-slate-500">admin@securevu.com</div>
              </div>
            </div>
          </div>
        </div>

        <Outlet />
      </main>
    </div>
  );
}

