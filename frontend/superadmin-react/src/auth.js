/**
 * Lightweight auth helpers for reading persisted role/token from localStorage.
 * These are used purely for client-side routing guards.
 * Real authorization decisions are always enforced on the backend.
 */

export function getStoredToken() {
    return localStorage.getItem("authToken") || null;
}

export function getStoredRole() {
    return localStorage.getItem("userRole") || null;
}

export function getStoredPermissions() {
    try {
        return JSON.parse(localStorage.getItem("userPermissions") || "[]");
    } catch {
        return [];
    }
}

export function clearAuth() {
    localStorage.removeItem("authToken");
    localStorage.removeItem("userRole");
    localStorage.removeItem("userPermissions");
}
