import { useEffect, useState } from "react";
import { DollarSign, AlertCircle, Ban ,TrendingUp } from "lucide-react";
import { fetchClients } from "../api/clients";

function estimateAmountByPlan(plan) {
  const key = (plan || "").toLowerCase();
  if (key.includes("pro") || key.includes("professional")) return 2499;
  if (key.includes("enterprise")) return 4999;
  if (key.includes("basic")) return 999;
  return 1499;
}

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

export default function BillingOverview() {
  const [stats, setStats] = useState({
    totalActive: 0,
    totalRevenue: 0,
    expiringSoon: 0,
    suspended: 0,
  });

  const [renewals, setRenewals] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadBillingData() {
      try {
        const clients = await fetchClients();
        const now = new Date();

        const normalized = Array.isArray(clients) ? clients : [];
        const totalActive = normalized.filter((c) => !!c.is_active).length;
        const totalRevenue = normalized.reduce(
          (sum, c) => sum + estimateAmountByPlan(c.subscription_plan),
          0
        );

        const renewalRows = normalized
          .filter((c) => !!c.next_billing_date)
          .map((c) => {
            const d = new Date(c.next_billing_date);
            const daysUntil = Number.isNaN(d.getTime())
              ? 0
              : Math.ceil((d.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
            return {
              id: c.id,
              client_name: c.name,
              plan: c.subscription_plan || "Standard",
              amount: estimateAmountByPlan(c.subscription_plan),
              renewal_date: formatDate(c.next_billing_date),
              days_until: daysUntil,
              status: c.is_active ? "Active" : "Suspended",
            };
          })
          .filter((r) => r.days_until >= 0 && r.days_until <= 60)
          .sort((a, b) => a.days_until - b.days_until);

        const expiringSoon = renewalRows.filter((r) => r.days_until <= 14).length;
        const suspended = normalized.filter((c) => !c.is_active).length;

        setStats({ totalActive, totalRevenue, expiringSoon, suspended });
        setRenewals(renewalRows);
      } catch (err) {
        setError("Failed to load billing overview");
      }
    }

    loadBillingData();
  }, []);

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div className="card p-4">
          <div className="mb-2 flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-slate-500">
            <span>Total Active</span>
            <TrendingUp size={16} className="text-emerald-600" />
          </div>
          <div className="text-2xl font-bold text-slate-900">{stats.totalActive}</div>
        </div>

        <div className="card p-4">
          <div className="mb-2 flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-slate-500">
            <span>Total Revenue</span>
            <DollarSign size={16} className="text-slate-700" />
          </div>
          <div className="text-2xl font-bold text-slate-900">${stats.totalRevenue?.toLocaleString()}</div>
        </div>

        <div className="card p-4">
          <div className="mb-2 flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-slate-500">
            <span>Expiring Soon</span>
            <AlertCircle size={16} className="text-amber-600" />
          </div>
          <div className="text-2xl font-bold text-slate-900">{stats.expiringSoon}</div>
        </div>

        <div className="card p-4">
          <div className="mb-2 flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-slate-500">
            <span>Suspended</span>
            <Ban size={16} className="text-red-600" />
          </div>
          <div className="text-2xl font-bold text-slate-900">{stats.suspended}</div>
        </div>
      </div>

      <div className="card overflow-hidden">
        {error ? <p className="p-4 text-sm text-red-600">{error}</p> : null}
        <div className="border-b border-slate-200 px-4 py-4">
          <div>
            <h3 className="text-base font-semibold text-slate-900">Upcoming Renewals</h3>
            <p className="text-sm text-slate-500">Subscriptions renewing in the next 60 days</p>
          </div>
        </div>

        <table className="min-w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
              <th className="px-4 py-3">Client Name</th>
              <th className="px-4 py-3">Subscription Plan</th>
              <th className="px-4 py-3">Billing Amount</th>
              <th className="px-4 py-3">Renewal Date</th>
              <th className="px-4 py-3">Days Until</th>
              <th className="px-4 py-3">Status</th>
            </tr>
          </thead>

          <tbody>
            {renewals.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-8 text-center text-sm text-slate-500">No upcoming renewals.</td>
              </tr>
            )}

            {renewals.map((item) => (
              <tr key={item.id} className="border-b border-slate-100 text-slate-700 last:border-b-0">
                <td className="px-4 py-3 font-medium text-slate-900">{item.client_name}</td>
                <td className="px-4 py-3">{item.plan}</td>
                <td className="px-4 py-3">${item.amount}</td>
                <td className="px-4 py-3">{item.renewal_date}</td>
                <td className="px-4 py-3">{item.days_until} days</td>
                <td className="px-4 py-3">
                  <span className="inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700">
                    {item.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

    </div>
  );
}
