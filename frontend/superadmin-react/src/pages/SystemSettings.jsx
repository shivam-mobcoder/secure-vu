import React, { useState } from 'react';
import { Camera, Save, Search, Bell } from 'lucide-react';
import '../styles/systemsettings.css';

export default function SystemSettings() {
    const [selectedDevice, setSelectedDevice] = useState('Lobby Cam 01 (Logitech Brio)');

    const devices = [
        'Lobby Cam 01 (Logitech Brio)',
        'Side Entrance (Axis M30)',
        'RTSP Stream...'
    ];

    const handleSave = () => {
        alert(`Configuration saved: ${selectedDevice}`);
    };

    return (
        <div className="ss-page">
            {/* Top Bar */}
            <div className="ss-top-bar">
                <div className="ss-global-search">
                    <Search size={18} color="#94a3b8" />
                    <input type="text" placeholder="Search clients, subscriptions..." className="ss-global-search-input" />
                </div>
                <div className="ss-top-actions">
                    <button className="ss-notification-btn" style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4 }}>
                        <Bell size={20} color="#64748b" />
                    </button>
                </div>
            </div>

            {/* Header Area */}
            <div className="ss-header">
                <div className="ss-title-section">
                    <h1 className="ss-title">System Configuration</h1>
                    <p className="ss-subtitle">Adjust global security parameters and device settings.</p>
                </div>
                <button className="ss-save-btn" onClick={handleSave}>
                    <Save size={16} />
                    Save Changes
                </button>
            </div>

            {/* Main Configuration Card */}
            <div className="ss-card">
                <div className="ss-section-header">
                    <div className="ss-section-icon">
                        <Camera size={24} />
                    </div>
                    <div className="ss-section-title-group">
                        <h2 className="ss-section-title">Device Configuration</h2>
                        <p className="ss-section-subtitle">Manage connected camera hardware.</p>
                    </div>
                </div>

                <div className="ss-form-group">
                    <label className="ss-label">Primary Input Device</label>
                    <select
                        className="ss-select"
                        value={selectedDevice}
                        onChange={(e) => setSelectedDevice(e.target.value)}
                    >
                        {devices.map((device) => (
                            <option key={device} value={device}>
                                {device}
                            </option>
                        ))}
                    </select>
                </div>
            </div>
        </div>
    );
}
