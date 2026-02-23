import { Navigate, Outlet } from "react-router-dom";
import { getStoredRole, getStoredToken } from "../auth";

/**
 * Route guard that renders child routes only when the stored role
 * matches one of the values in the `allowed` array.
 *
 * If there is no token at all → redirect to /auth (not logged in).
 * If token exists but role is wrong → redirect to /auth (wrong role).
 *
 * Usage:
 *   <Route element={<RequireRole allowed={["admin"]} />}>
 *     <Route path="face/enroll" element={<FaceEnrollment />} />
 *   </Route>
 */
export default function RequireRole({ allowed = [] }) {
    const token = getStoredToken();
    const role = getStoredRole();

    if (!token || !allowed.includes(role)) {
        return <Navigate to="/auth" replace />;
    }

    return <Outlet />;
}
