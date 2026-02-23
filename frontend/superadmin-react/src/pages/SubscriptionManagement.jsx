import { useState, useMemo, useEffect } from "react";
import { Funnel, Plus, Pencil, Trash2 } from "lucide-react";
import { fetchClients } from "../api/clients";

function formatDate(value) {
  if (!value) return "—";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return String(value);
  return dt.toLocaleDateString(undefined, {
    month: "short",
    day: "2-digit",
    year: "numeric",
  });
}

function estimateAmountByPlan(plan) {
  const key = (plan || "").toLowerCase();
  if (key.includes("pro") || key.includes("professional")) return 2499;
  if (key.includes("enterprise")) return 4999;
  if (key.includes("basic")) return 999;
  return 1499;
}

export default function SubscriptionManagement() {
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [cycleFilter, setCycleFilter] = useState("");

  const perPage = 8;

  useEffect(() => {
    let cancelled = false;

    async function loadPlans() {
      setLoading(true);
      setError("");
      try {
        const clients = await fetchClients();
        const normalized = Array.isArray(clients)
          ? clients.map((c) => ({
              id: c.id,
              name: c.subscription_plan || "Standard",
              modules: ["Video Monitoring", "Alerts"],
              amount: estimateAmountByPlan(c.subscription_plan),
              cycle: c.billing_cycle || "Monthly",
              status: c.is_active ? "Active" : "Inactive",
              created_at: formatDate(c.created_at),
            }))
          : [];
        if (!cancelled) {
          setPlans(normalized);
        }
      } catch (err) {
        if (!cancelled) {
          setError("Failed to load plans");
          setPlans([]);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadPlans();
    return () => {
      cancelled = true;
    };
  }, []);

  const filtered = useMemo(() => {
    return plans.filter(
      (p) =>
        (!search ||
          p.name?.toLowerCase().includes(search.toLowerCase())) &&
        (!statusFilter || p.status === statusFilter) &&
        (!cycleFilter || p.cycle === cycleFilter)
    );
  }, [plans, search, statusFilter, cycleFilter]);

  const totalPages = Math.ceil(filtered.length / perPage);

  const paginated = useMemo(() => {
    const start = (page - 1) * perPage;
    return filtered.slice(start, start + perPage);
  }, [filtered, page]);

  const startItem = filtered.length === 0 ? 0 : (page - 1) * perPage + 1;
  const endItem = Math.min(page * perPage, filtered.length);

  const statusBadgeClass = (status) =>
    (status || "").toLowerCase() === "active"
      ? "inline-flex rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700"
      : "inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700";

  return (
    <div className="space-y-4">
      <div className="card p-4">
        <div className="flex flex-wrap items-center gap-3">
          <input
            type="text"
            placeholder="Search plans..."
            className="field max-w-xs"
            value={search}
            onChange={(e) => {
              setPage(1);
              setSearch(e.target.value);
            }}
          />

          <div className="relative">
            <Funnel size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <select
              className="field pl-8"
              value={statusFilter}
              onChange={(e) => {
                setPage(1);
                setStatusFilter(e.target.value);
              }}
            >
              <option value="">Status</option>
              <option value="Active">Active</option>
              <option value="Inactive">Inactive</option>
            </select>
          </div>

          <div className="relative">
            <Funnel size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <select
              className="field pl-8"
              value={cycleFilter}
              onChange={(e) => {
                setPage(1);
                setCycleFilter(e.target.value);
              }}
            >
              <option value="">Billing Cycle</option>
              <option value="Monthly">Monthly</option>
              <option value="Annual">Annual</option>
            </select>
          </div>

          <button className="btn-primary ml-auto">
            <Plus size={14} />
            Create New Plan
          </button>
        </div>
      </div>

      <div className="card overflow-hidden">
        {loading && <p className="p-4 text-sm text-slate-500">Loading plans...</p>}
        {!loading && error && <p className="p-4 text-sm text-red-600">{error}</p>}

        <table className="min-w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
              <th className="px-4 py-3">Plan Name</th>
              <th className="px-4 py-3">Included Modules</th>
              <th className="px-4 py-3">Billing Amount</th>
              <th className="px-4 py-3">Billing Cycle</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Created Date</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>

          <tbody>
            {paginated.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-sm text-slate-500">No plans found.</td>
              </tr>
            )}

            {paginated.map((plan) => (
              <tr key={plan.id} className="border-b border-slate-100 text-slate-700 last:border-b-0">
                <td className="px-4 py-3 font-medium text-slate-900">{plan.name}</td>

                <td className="px-4 py-3">
                  {plan.modules?.map((m) => (
                    <span
                      key={m}
                      className="mr-2 inline-flex rounded-full bg-slate-100 px-2 py-1 text-xs font-medium text-slate-600"
                    >
                      {m}
                    </span>
                  ))}
                </td>

                <td className="px-4 py-3">${plan.amount}</td>
                <td className="px-4 py-3">{plan.cycle}</td>

                <td className="px-4 py-3">
                  <span className={statusBadgeClass(plan.status)}>
                    {plan.status}
                  </span>
                </td>

                <td className="px-4 py-3">{plan.created_at}</td>

                <td className="px-4 py-3">
                  <div className="flex items-center gap-3 text-slate-600">
                    <Pencil size={15} className="cursor-pointer hover:text-slate-900" />
                    <Trash2 size={15} className="cursor-pointer hover:text-slate-900" />
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className="flex items-center justify-between border-t border-slate-200 px-4 py-3 text-sm text-slate-600">
          <span>
            Showing {startItem} to {endItem} of {filtered.length} results
          </span>

          <div className="flex items-center gap-2">
            {[...Array(totalPages)].map((_, i) => (
              <button
                type="button"
                key={i}
                className={
                  page === i + 1
                    ? "h-8 min-w-8 rounded-md bg-slate-900 px-2 text-xs font-semibold text-white"
                    : "h-8 min-w-8 rounded-md border border-slate-200 bg-white px-2 text-xs font-semibold text-slate-600 hover:bg-slate-50"
                }
                onClick={() => setPage(i + 1)}
              >
                {i + 1}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
