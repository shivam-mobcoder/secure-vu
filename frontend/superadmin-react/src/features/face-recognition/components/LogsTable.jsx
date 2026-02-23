import React from "react";

const mockData = [
    {
        name: "Sarah Connor",
        role: "Employee",
        time: "2023-10-25 14:30",
        score: 98,
        status: "Granted",
        device: "Lobby-01",
    },
];

export default function LogsTable() {
    return (
        <div className="bg-white rounded-xl shadow-sm overflow-hidden">
            <table className="w-full text-sm">
                <thead className="bg-gray-50 text-gray-600 text-left">
                    <tr>
                        <th className="p-4">Name</th>
                        <th>Persona</th>
                        <th>Date & Time</th>
                        <th>Match Score</th>
                        <th>Status</th>
                        <th>Device</th>
                    </tr>
                </thead>
                <tbody>
                    {mockData.map((log, i) => (
                        <tr key={i} className="border-t">
                            <td className="p-4 font-medium">{log.name}</td>
                            <td>{log.role}</td>
                            <td>{log.time}</td>
                            <td>{log.score}%</td>
                            <td>
                                <span className="px-2 py-1 text-xs rounded-full bg-green-100 text-green-600">
                                    {log.status}
                                </span>
                            </td>
                            <td>{log.device}</td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}
