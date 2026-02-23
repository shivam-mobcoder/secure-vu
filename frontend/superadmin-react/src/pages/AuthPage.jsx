import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

const ROLES = [
  { value: "super_admin", label: "Super Admin" },
  { value: "admin", label: "Admin" },
  { value: "member", label: "Member" },
];

async function apiPost(path, payload) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    credentials: "include",
    body: JSON.stringify(payload),
  });

  let body = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }

  if (!res.ok) {
    const reason = body?.error || body?.message || `Request failed (${res.status})`;
    throw new Error(reason);
  }

  return body;
}

async function fetchMe(token) {
  const res = await fetch("/me", {
    headers: {
      Accept: "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    credentials: "include",
  });

  if (!res.ok) {
    throw new Error("Could not resolve current user");
  }

  return res.json();
}

const BACKEND_ORIGIN = import.meta.env.VITE_BACKEND_ORIGIN || "https://localhost:8000";

export default function AuthPage() {
  const navigate = useNavigate();
  const [mode, setMode] = useState("login");

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("admin");
  const [clientId, setClientId] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const title = useMemo(
    () => (mode === "login" ? "Login to SecureVU" : "Create your account"),
    [mode]
  );

  const subtitle = useMemo(
    () =>
      mode === "login"
        ? "Sign in and we will route you to the right experience by role."
        : "Choose a predefined role and create an account.",
    [mode]
  );

  async function handleSubmit(e) {
    e.preventDefault();
    setLoading(true);
    setError("");

    try {
      const payload = {
        email: email.trim(),
        password,
        role,
        ...(clientId.trim() ? { client_id: Number(clientId) } : {}),
      };

      const auth = await apiPost(mode === "login" ? "/login" : "/signup", payload);
      const token = auth?.token || "";
      if (!token) throw new Error("Authentication token not returned");

      localStorage.setItem("authToken", token);

      const me = await fetchMe(token);
      const normalizedRole = String(me?.role || "").toLowerCase().replace(/[-\s]+/g, "_");

      // Persist role for client-side route guards
      localStorage.setItem("userRole", normalizedRole);

      if (normalizedRole === "super_admin") {
        navigate("/super-admin/dashboard/client-management", { replace: true });
      } else if (normalizedRole === "admin") {
        navigate("/admin/dashboard/face/enroll", { replace: true });
      } else {
        const next = `${BACKEND_ORIGIN}/?token=${encodeURIComponent(token)}`;
        window.location.assign(next);
      }
    } catch (err) {
      setError(err?.message || "Authentication failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 px-4 py-10">
      <div className="mx-auto w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-5">
          <h1 className="text-2xl font-bold text-slate-900">{title}</h1>
          <p className="mt-1 text-sm text-slate-500">{subtitle}</p>
        </div>

        <div className="mb-5 grid grid-cols-2 rounded-lg bg-slate-100 p-1">
          <button
            type="button"
            onClick={() => setMode("login")}
            className={
              mode === "login"
                ? "rounded-md bg-white px-3 py-2 text-sm font-semibold text-slate-900"
                : "rounded-md px-3 py-2 text-sm font-medium text-slate-600"
            }
          >
            Login
          </button>
          <button
            type="button"
            onClick={() => setMode("signup")}
            className={
              mode === "signup"
                ? "rounded-md bg-white px-3 py-2 text-sm font-semibold text-slate-900"
                : "rounded-md px-3 py-2 text-sm font-medium text-slate-600"
            }
          >
            Sign Up
          </button>
        </div>

        <form className="space-y-3" onSubmit={handleSubmit}>
          <div>
            <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">Email</label>
            <input
              type="email"
              className="field"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">Password</label>
            <input
              type="password"
              className="field"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">Role</label>
            <select className="field" value={role} onChange={(e) => setRole(e.target.value)}>
              {ROLES.map((r) => (
                <option key={r.value} value={r.value}>
                  {r.label}
                </option>
              ))}
            </select>
          </div>

          {mode === "signup" ? (
            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">
                Client ID (optional for super admin)
              </label>
              <input
                type="number"
                className="field"
                value={clientId}
                onChange={(e) => setClientId(e.target.value)}
                placeholder="e.g. 1"
              />
            </div>
          ) : null}

          {error ? <p className="text-sm text-red-600">{error}</p> : null}

          <button type="submit" disabled={loading} className="btn-primary w-full justify-center">
            {loading ? "Please wait..." : mode === "login" ? "Login" : "Create account"}
          </button>
        </form>
      </div>
    </div>
  );
}
