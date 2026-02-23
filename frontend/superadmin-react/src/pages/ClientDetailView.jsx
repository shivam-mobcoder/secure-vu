import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Pencil, Ban, X } from "lucide-react";

const API_CLIENTS = "/api/super-admin/clients";

function getAuthHeaders() {
  const token = localStorage.getItem("authToken") || "";
  return token
    ? { Accept: "application/json", Authorization: `Bearer ${token}` }
    : { Accept: "application/json" };
}

function formatDate(value) {
  if (!value) return "—";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return String(value);
  return dt.toLocaleDateString(undefined, {
    month: "long",
    day: "2-digit",
    year: "numeric",
  });
}

export default function ClientDetailView() {
  const navigate = useNavigate();
  const { id } = useParams();
  const [client, setClient] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadClient() {
      setLoading(true);
      setError("");
      try {
        const res = await fetch(API_CLIENTS, {
          credentials: "include",
          headers: getAuthHeaders(),
        });
        if (!res.ok) {
          throw new Error(`Failed with status ${res.status}`);
        }
        const rows = await res.json();
        const found = Array.isArray(rows)
          ? rows.find((row) => String(row.id) === String(id))
          : null;

        if (!cancelled) {
          setClient(found || null);
          if (!found) {
            setError("Client not found");
          }
        }
      } catch (e) {
        if (!cancelled) {
          setError(e?.message || "Could not load client details");
          setClient(null);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadClient();
    return () => {
      cancelled = true;
    };
  }, [id]);

  const status = useMemo(
    () => (client?.is_active ? "Active" : "Suspended"),
    [client]
  );

  if (loading) {
    return <div className="card p-5 text-sm text-slate-500">Loading client details...</div>;
  }

  if (error) {
    return (
      <div className="card space-y-3 p-5">
        <p className="text-sm text-red-600">{error}</p>
        <button
          className="btn-secondary"
          onClick={() => navigate("../../client-management", { relative: "path" })}
        >
          Back
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <button
        className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900"
        onClick={() => navigate("../../client-management", { relative: "path" })}
        type="button"
      >
        <ArrowLeft size={16} />
        Back to Client Management
      </button>

      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-xl font-bold text-slate-900">Client Detail View</h3>
          <p className="mt-1 text-sm text-slate-500">
            Complete client information and subscription details
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button className="btn-secondary">
            <Pencil size={14} /> Edit
          </button>
          <button className="btn-secondary">
            <Ban size={14} /> Suspend
          </button>
          <button className="btn-secondary">
            <X size={14} /> Cancel
          </button>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="card p-5">
          <h3 className="mb-4 text-base font-semibold text-slate-900">Client Information</h3>

          <div className="space-y-3 text-sm">
            <div>
              <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Client Name</label>
              <p className="mt-1 text-slate-900">{client?.name || "—"}</p>
            </div>

            <div>
              <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Address</label>
              <p className="mt-1 text-slate-700">—</p>
            </div>

            <div>
              <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Email</label>
              <p className="mt-1 text-slate-700">{client?.email || "—"}</p>
            </div>

            <div>
              <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Mobile Number</label>
              <p className="mt-1 text-slate-700">{client?.phone || "—"}</p>
            </div>

            <div>
              <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Client Type</label>
              <div className="mt-1 inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700">
                {client?.customer_type || "—"}
              </div>
            </div>
          </div>
        </div>

        <div className="card p-5">
          <h3 className="mb-4 text-base font-semibold text-slate-900">Subscription Information</h3>
          <div className="space-y-3 text-sm">
            <div>
              <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Subscription Plan</label>
              <p className="mt-1 text-slate-900">{client?.subscription_plan || "—"}</p>
            </div>

            <div>
              <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Billing Amount</label>
              <p className="mt-1 text-slate-700">—</p>
            </div>

            <div>
              <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Status</label>
              <div className="mt-1 inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700">{status}</div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Billing Cycle</label>
                <p className="mt-1 text-slate-700">{client?.billing_cycle || "—"}</p>
              </div>
              <div>
                <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Billing Date</label>
                <p className="mt-1 text-slate-700">{client?.billing_cycle || "—"}</p>
              </div>
            </div>

            <div>
              <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Renewal Date</label>
              <p className="mt-1 text-slate-700">{formatDate(client?.next_billing_date)}</p>
            </div>
          </div>
        </div>

        <div className="card p-5">
          <h3 className="mb-4 text-base font-semibold text-slate-900">Quick Stats</h3>

          <div className="space-y-4 text-sm">
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
              <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Total Paid</label>
              <h4 className="mt-1 text-2xl font-bold text-slate-900">$6,497.00</h4>
              <p className="text-slate-500">Last 3 months</p>
            </div>

            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
              <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Days Active</label>
              <h4 className="mt-1 text-2xl font-bold text-slate-900">60</h4>
              <p className="text-slate-500">Since Dec 14, 2025</p>
            </div>

            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
              <label className="text-xs font-semibold uppercase tracking-wide text-slate-500">Next Billing</label>
              <h4 className="mt-1 text-2xl font-bold text-slate-900">31</h4>
              <p className="text-slate-500">Days remaining</p>
            </div>
          </div>
        </div>
      </div>

      <div className="card overflow-hidden">
        <div className="border-b border-slate-200 px-4 py-3">
          <h3 className="text-base font-semibold text-slate-900">Activity & Logs</h3>
        </div>

        <table className="min-w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3">Description</th>
              <th className="px-4 py-3">Date</th>
              <th className="px-4 py-3">Status</th>
            </tr>
          </thead>
          <tbody>
            <tr className="text-slate-700">
              <td className="px-4 py-3">
                <span className="inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700">Payment</span>
              </td>
              <td className="px-4 py-3">Payment received - $2,499.00</td>
              <td className="px-4 py-3">2026-02-15</td>
              <td className="px-4 py-3">
                <span className="inline-flex rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700">Success</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
