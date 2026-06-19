import { useEffect, useState } from 'react';
import { PlayCircle, RefreshCw, Video } from 'lucide-react';
import { getStoredToken } from '../../../auth';

const BACKEND = import.meta.env.VITE_BACKEND_ORIGIN || '';

export default function Playback() {
    const [recordings, setRecordings] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    async function loadRecordings() {
        const token = getStoredToken();
        if (!token) {
            setError('Not authenticated');
            setLoading(false);
            return;
        }
        setLoading(true);
        setError('');
        try {
            const res = await fetch(`${BACKEND}/api/recordings?limit=50`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            if (!res.ok) {
                throw new Error(`HTTP ${res.status}`);
            }
            const data = await res.json();
            setRecordings(data.recordings || []);
        } catch (e) {
            setError(e.message || 'Failed to load recordings');
        } finally {
            setLoading(false);
        }
    }

    useEffect(() => {
        loadRecordings();
    }, []);

    function formatTs(iso) {
        if (!iso) return '—';
        try {
            return new Date(iso).toLocaleString();
        } catch {
            return iso;
        }
    }

    function formatSize(bytes) {
        const n = Number(bytes) || 0;
        if (n < 1024) return `${n} B`;
        if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
        return `${(n / (1024 * 1024)).toFixed(1)} MB`;
    }

    return (
        <div className="max-w-5xl">
            <div className="mb-6 flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900">Recording Playback</h1>
                    <p className="mt-1 text-sm text-slate-500">
                        Continuous 5-minute segments indexed from the VMS recorder.
                    </p>
                </div>
                <button
                    type="button"
                    onClick={loadRecordings}
                    className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                >
                    <RefreshCw size={16} />
                    Refresh
                </button>
            </div>

            {loading && (
                <div className="flex items-center gap-2 text-slate-500">
                    <Video size={18} />
                    Loading segments…
                </div>
            )}

            {error && !loading && (
                <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    {error}
                </div>
            )}

            {!loading && !error && recordings.length === 0 && (
                <div className="rounded-lg border border-slate-200 bg-white px-6 py-10 text-center text-slate-500">
                    No recording segments yet. Segments appear after continuous recording runs for a few minutes.
                </div>
            )}

            {!loading && recordings.length > 0 && (
                <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
                    <table className="min-w-full text-left text-sm">
                        <thead className="border-b border-slate-200 bg-slate-50 text-xs font-semibold uppercase tracking-wide text-slate-500">
                            <tr>
                                <th className="px-4 py-3">Camera</th>
                                <th className="px-4 py-3">Start</th>
                                <th className="px-4 py-3">End</th>
                                <th className="px-4 py-3">Size</th>
                                <th className="px-4 py-3">Play</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                            {recordings.map((seg) => (
                                <tr key={seg.id} className="hover:bg-slate-50">
                                    <td className="px-4 py-3 font-medium text-slate-900">
                                        Camera {seg.camera_id}
                                    </td>
                                    <td className="px-4 py-3 text-slate-600">{formatTs(seg.start_ts)}</td>
                                    <td className="px-4 py-3 text-slate-600">{formatTs(seg.end_ts)}</td>
                                    <td className="px-4 py-3 text-slate-600">{formatSize(seg.size_bytes)}</td>
                                    <td className="px-4 py-3">
                                        {seg.url ? (
                                            <a
                                                href={`${BACKEND}${seg.url}`}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="inline-flex items-center gap-1 text-sm font-medium text-green-700 hover:text-green-800"
                                            >
                                                <PlayCircle size={16} />
                                                Play
                                            </a>
                                        ) : (
                                            <span className="text-slate-400">—</span>
                                        )}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}
