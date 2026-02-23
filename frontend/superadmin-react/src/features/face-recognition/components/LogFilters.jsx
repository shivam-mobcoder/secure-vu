import React from "react";

export default function LogFilters() {
    return (
        <div className="bg-white p-4 rounded-xl shadow-sm flex flex-wrap gap-4 items-center">
            <input
                type="text"
                placeholder="Search logs..."
                className="border rounded-lg px-3 py-2 w-64 text-sm"
            />

            <select className="border rounded-lg px-3 py-2 text-sm">
                <option>Status</option>
                <option>Granted</option>
                <option>Denied</option>
                <option>Alert</option>
            </select>

            <select className="border rounded-lg px-3 py-2 text-sm">
                <option>Role</option>
                <option>Employee</option>
                <option>Visitor</option>
                <option>Admin</option>
            </select>

            <button className="ml-auto bg-black text-white px-4 py-2 rounded-lg text-sm">
                Export CSV
            </button>
        </div>
    );
}
