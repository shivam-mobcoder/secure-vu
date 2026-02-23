import { useState, useMemo, useEffect } from "react";
import { Funnel, Eye, Pencil, Ban, Plus } from "lucide-react";
import { useNavigate } from "react-router-dom";
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

function normalizeClient(row) {
  const status = row.is_active ? "Active" : "Suspended";
  return {
    id: row.id,
    name: row.name || "—",
    module: row.subscription_plan || "—",
    billing: row.billing_cycle || "—",
    type: row.customer_type || "—",
    status,
    renewal: formatDate(row.next_billing_date),
  };
}

export default function ClientManagement() {
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [typeFilter, setTypeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [clientsData, setClientsData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");


  useEffect(() => {
    let cancelled = false;

    async function loadClients() {
      setLoading(true);
      setError("");

      try {
        const rows = await fetchClients();
        if (!cancelled) {
          const mapped = Array.isArray(rows)
            ? rows.map(normalizeClient)
            : [];
          setClientsData(mapped);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e?.message || "Could not load clients");
          setClientsData([]);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadClients();
    return () => {
      cancelled = true;
    };
  }, []);

  const perPage = 8;

  const typeOptions = useMemo(
    () => Array.from(new Set(clientsData.map((c) => c.type).filter(Boolean))),
    [clientsData]
  );
const filtered = useMemo(() => {
  return clientsData.filter(
    (c) =>
      (!search ||
        c.name.toLowerCase().includes(search.toLowerCase())) &&
      (!typeFilter || c.type === typeFilter) &&
      (!statusFilter || c.status === statusFilter)
  );
}, [clientsData, search, typeFilter, statusFilter]);

  const totalPages = Math.ceil(filtered.length / perPage);

  const paginated = useMemo(() => {
    const start = (page - 1) * perPage;
    return filtered.slice(start, start + perPage);
  }, [page, filtered]);

  const startItem = filtered.length === 0 ? 0 : (page - 1) * perPage + 1;
  const endItem = Math.min(page * perPage, filtered.length);

  const statusBadgeClass = (status) =>
    status === "Active"
      ? "inline-flex rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700"
      : "inline-flex rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700";

  return (
    <div className="space-y-4">
      <div className="card p-4">
        <div className="flex flex-wrap items-center gap-3">
          <input
            type="text"
            placeholder="Search client..."
            className="field max-w-xs"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />

          <button className="btn-secondary" onClick={() => setPage(1)}>
            Search
          </button>

          <div className="relative">
            <Funnel size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <select
              className="field pl-8"
              value={typeFilter}
              onChange={(e) => {
                setPage(1);
                setTypeFilter(e.target.value);
              }}
            >
              <option value="">All Types</option>
              {typeOptions.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>
          </div>

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
              <option value="Suspended">Suspended</option>
            </select>
          </div>

          <button
            className="btn-primary ml-auto"
            onClick={() => navigate("../client/new", { relative: "path" })}
          >
            <Plus size={14} />
            Add New Client
          </button>
        </div>
      </div>

      <div className="card overflow-hidden">
        {loading && <p className="p-4 text-sm text-slate-500">Loading clients...</p>}
        {!loading && error && <p className="p-4 text-sm text-red-600">Error loading clients: {error}</p>}

        <table className="min-w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
              <th className="px-4 py-3">Client Name</th>
              <th className="px-4 py-3">Subscription Module</th>
              <th className="px-4 py-3">Billing Date</th>
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Renewal Date</th>
              <th className="px-4 py-3">Actions</th>
            </tr>
          </thead>

          <tbody>
            {!loading && !error && paginated.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-sm text-slate-500">No clients found.</td>
              </tr>
            )}

            {paginated.map((client) => (
              <tr key={client.id} className="border-b border-slate-100 text-slate-700 last:border-b-0">
                <td className="px-4 py-3 font-medium text-slate-900">{client.name}</td>
                <td className="px-4 py-3">{client.module}</td>
                <td className="px-4 py-3">{client.billing}</td>
                <td className="px-4 py-3">{client.type}</td>
                <td className="px-4 py-3">
                  <span className={statusBadgeClass(client.status)}>{client.status}</span>
                </td>
                <td className="px-4 py-3">{client.renewal}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-3 text-slate-600">
                  <Eye
                    size={15}
                    className="cursor-pointer hover:text-slate-900"
                    onClick={() =>
                      navigate(`../client/${client.id}`, {
                        relative: "path",
                      })
                    }
                  />
                  <Pencil size={15} className="cursor-pointer hover:text-slate-900" />
                  <Ban size={15} className="cursor-pointer hover:text-slate-900" />
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
