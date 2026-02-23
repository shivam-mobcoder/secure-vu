import { useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  Save,
  X,
  ArrowLeft
} from "lucide-react";

export default function AddClient() {
  const navigate = useNavigate();

  const [form, setForm] = useState({
    name: "",
    address: "",
    email: "",
    mobile: "",
    client_type: "",
    subscription_plan: "",
    billing_amount: "",
    subscription_status: "",
    billing_cycle: "",
    billing_date: "",
    renewal_date: "",
    auto_renew: false,
    private_users: 0,
    business_users: 0,
    public_places: 0,
    notes: "",
    account_manager: "",
  });

  function handleChange(e) {
    const { name, value, type, checked } = e.target;
    setForm({
      ...form,
      [name]: type === "checkbox" ? checked : value,
    });
  }

  function handleSubmit(e) {
    e.preventDefault();
    console.log("Form Submitted:", form);
    // TODO: call createClient API here
  }

  const inputClass = "field";
  const labelClass = "mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500";

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <button
          className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 hover:text-slate-900"
          onClick={() => navigate("../../client-management", { relative: "path" })}
          type="button"
        >
          <ArrowLeft size={16} />
          Back to Client Management
        </button>

        <div className="flex items-center gap-2">
          <button className="btn-secondary" onClick={() => navigate(-1)} type="button">
            <X size={16} />
            Cancel
          </button>
          <button className="btn-primary" type="submit" form="add-client-form">
            <Save size={16} />
            Save Client
          </button>
        </div>
      </div>

      <form id="add-client-form" onSubmit={handleSubmit} className="space-y-4">
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="card p-5">
            <h3 className="mb-4 text-base font-semibold text-slate-900">Client Information</h3>

            <div className="space-y-3">
              <div>
                <label className={labelClass}>Client Name *</label>
                <input className={inputClass} name="name" placeholder="Enter client name" value={form.name} onChange={handleChange} required />
              </div>

              <div>
                <label className={labelClass}>Address *</label>
                <textarea className={inputClass} name="address" placeholder="Enter complete address" value={form.address} onChange={handleChange} />
              </div>

              <div>
                <label className={labelClass}>Email *</label>
                <input className={inputClass} name="email" type="email" placeholder="Enter email" value={form.email} onChange={handleChange} />
              </div>

              <div>
                <label className={labelClass}>Mobile Number *</label>
                <input className={inputClass} name="mobile" placeholder="Enter mobile number" value={form.mobile} onChange={handleChange} />
              </div>

              <div>
                <label className={labelClass}>Client Type *</label>
                <select className={inputClass} name="client_type" value={form.client_type} onChange={handleChange}>
                  <option value="">Select client type</option>
                  <option value="Business">Business</option>
                  <option value="Enterprise">Enterprise</option>
                </select>
              </div>
            </div>
          </div>

          <div className="card p-5">
            <h3 className="mb-4 text-base font-semibold text-slate-900">Subscription Information</h3>

            <div className="space-y-3">
              <div>
                <label className={labelClass}>Subscription Plan *</label>
                <select className={inputClass} name="subscription_plan" value={form.subscription_plan} onChange={handleChange}>
                  <option value="">Select subscription plan</option>
                  <option value="Basic">Basic</option>
                  <option value="Pro">Pro</option>
                </select>
              </div>

              <div>
                <label className={labelClass}>Billing Amount *</label>
                <input className={inputClass} name="billing_amount" placeholder="Enter billing amount" value={form.billing_amount} onChange={handleChange} />
              </div>

              <div>
                <label className={labelClass}>Subscription Status *</label>
                <select className={inputClass} name="subscription_status" value={form.subscription_status} onChange={handleChange}>
                  <option value="">Select status</option>
                  <option value="Active">Active</option>
                  <option value="Trial">Trial</option>
                  <option value="Expired">Expired</option>
                </select>
              </div>

              <div>
                <label className={labelClass}>Billing Cycle *</label>
                <select className={inputClass} name="billing_cycle" value={form.billing_cycle} onChange={handleChange}>
                  <option value="">Select billing cycle</option>
                  <option value="Monthly">Monthly</option>
                  <option value="Yearly">Yearly</option>
                </select>
              </div>

              <div>
                <label className={labelClass}>Billing Date *</label>
                <input className={inputClass} name="billing_date" placeholder="Enter billing date" value={form.billing_date} onChange={handleChange} />
              </div>

              <div>
                <label className={labelClass}>Renewal Date *</label>
                <input className={inputClass} type="date" name="renewal_date" value={form.renewal_date} onChange={handleChange} />
              </div>

              <div className="flex items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
                <label className="text-sm font-medium text-slate-700">Auto Renew</label>
                <button
                  type="button"
                  className={
                    form.auto_renew
                      ? "h-6 w-11 rounded-full bg-slate-900 p-0.5"
                      : "h-6 w-11 rounded-full bg-slate-300 p-0.5"
                  }
                  onClick={() => setForm({ ...form, auto_renew: !form.auto_renew })}
                >
                  <span
                    className={
                      form.auto_renew
                        ? "block h-5 w-5 translate-x-5 rounded-full bg-white transition"
                        : "block h-5 w-5 rounded-full bg-white transition"
                    }
                  />
                </button>
              </div>
            </div>
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <div className="card p-5">
            <h3 className="mb-4 text-base font-semibold text-slate-900">User Capacity</h3>
            <div className="space-y-3">
              <div>
                <label className={labelClass}>Private Users *</label>
                <input className={inputClass} type="number" name="private_users" value={form.private_users} onChange={handleChange} />
              </div>
              <div>
                <label className={labelClass}>Business Users *</label>
                <input className={inputClass} type="number" name="business_users" value={form.business_users} onChange={handleChange} />
              </div>
              <div>
                <label className={labelClass}>Public Places *</label>
                <input className={inputClass} type="number" name="public_places" value={form.public_places} onChange={handleChange} />
              </div>
            </div>
          </div>

          <div className="card p-5">
            <h3 className="mb-4 text-base font-semibold text-slate-900">Additional Information</h3>
            <div className="space-y-3">
              <div>
                <label className={labelClass}>Internal Notes</label>
                <textarea className={inputClass} name="notes" value={form.notes} onChange={handleChange} />
              </div>
              <div>
                <label className={labelClass}>Account Manager</label>
                <select className={inputClass} name="account_manager" value={form.account_manager} onChange={handleChange}>
                  <option value="">Assign account manager</option>
                  <option value="Manager1">Manager 1</option>
                  <option value="Manager2">Manager 2</option>
                </select>
              </div>
            </div>
          </div>
        </div>
      </form>
    </div>
  );
}
