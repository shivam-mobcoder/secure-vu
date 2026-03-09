import { Routes, Route, Navigate } from "react-router-dom";

import Landing from "./pages/Landing";
import AuthPage from "./pages/AuthPage";
import RecognitionLogs from "./features/face-recognition/pages/RecognitionLogs";
import FaceEnrollment from "./features/face-recognition/pages/FaceEnrollment";
import AdminFeed from "./features/face-recognition/pages/AdminFeed";
import SelfEnrollment from "./features/face-recognition/pages/SelfEnrollment";
import CorporateAccess from "./features/face-recognition/pages/CorporateAccess";

import SubscriptionManagement from "./pages/SubscriptionManagement";
import ClientManagement from "./pages/ClientManagement";
import BillingOverview from "./pages/BillingOverview";
import Settings from "./pages/Settings";
import ClientDetailView from "./pages/ClientDetailView";
import AddClient from "./pages/AddClient";
import UserManagement from "./pages/UserManagement";
import SystemSettings from "./pages/SystemSettings";
import AdminLayout from "./components/AdminLayout";
import AdminDashboardLayout from "./components/AdminDashboardLayout";
import RequireRole from "./components/RequireRole";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/home" replace />} />
      <Route path="/home" element={<Landing />} />
      <Route path="/auth" element={<AuthPage />} />

      {/* ── Public: Self-enrollment via share link (no login) ──────── */}
      <Route path="/enroll/:token" element={<SelfEnrollment />} />

      {/* ── Super-admin area (super_admin only) ─────────────────────── */}
      <Route path="/super-admin/dashboard" element={<AdminLayout />}>
        <Route index element={<Navigate to="client-management" replace />} />
        <Route path="client-management" element={<ClientManagement />} />
        <Route path="client/new" element={<AddClient />} />
        <Route path="client/:id" element={<ClientDetailView />} />
        <Route path="subscription-management" element={<SubscriptionManagement />} />
        <Route path="billing-overview" element={<BillingOverview />} />
        <Route path="settings" element={<Settings />} />
      </Route>

      {/* ── Admin area (admin + member role) ─────────────────────────── */}
      <Route element={<RequireRole allowed={["admin", "member"]} />}>
        <Route path="/admin/dashboard" element={<AdminDashboardLayout />}>
          <Route index element={<Navigate to="face/enroll" replace />} />
          <Route path="face/enroll" element={<FaceEnrollment />} />
          <Route path="face/logs" element={<RecognitionLogs />} />
          <Route path="live-feed" element={<AdminFeed />} />
          <Route path="users" element={<UserManagement />} />
          <Route path="system-settings" element={<SystemSettings />} />
          <Route path="face/corporate-access" element={<CorporateAccess />} />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/home" replace />} />
    </Routes>
  );
}
