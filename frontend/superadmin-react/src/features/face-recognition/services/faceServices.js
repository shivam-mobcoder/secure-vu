/**
 * faceServices.js
 * API layer for face enrollment, listing, deletion, and shareable link generation.
 * All endpoints require an Authorization header with the JWT token,
 * except for token-based enrollment (share link flow).
 */

import { getStoredToken } from '../../../auth';
export { getStoredToken };

const BACKEND = import.meta.env.VITE_BACKEND_ORIGIN || '';

function authHeaders(extra = {}) {
    const token = getStoredToken();
    return {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...extra,
    };
}

async function handleResponse(res) {
    if (!res.ok) {
        let errorMsg = `HTTP ${res.status}`;
        try {
            const body = await res.json();
            errorMsg = body.message || body.error || errorMsg;
        } catch {
            try { errorMsg = await res.text(); } catch { /* ignore */ }
        }
        throw new Error(errorMsg);
    }
    const ct = res.headers.get('content-type') || '';
    if (ct.includes('application/json')) return res.json();
    return res.text();
}

/**
 * Enroll a person using base64-encoded webcam frames.
 * @param {string} name - Person's display name
 * @param {string[]} frames - Array of base64 data-URIs (image/jpeg)
 * @returns {Promise<{status: string, message: string, liveness_score: number, frames_used: number}>}
 */
export async function enrollFrames(name, frames) {
    const res = await fetch(`${BACKEND}/api/face/enroll-frames`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ name, frames }),
    });
    return handleResponse(res);
}

/**
 * List all enrolled faces for this admin's client.
 * @returns {Promise<{faces: string[]}>}
 */
export async function listFaces() {
    const res = await fetch(`${BACKEND}/api/face/list`, {
        headers: authHeaders(),
    });
    return handleResponse(res);
}

/**
 * Delete an enrolled face by name.
 * @param {string} name
 * @returns {Promise<{status: string, name: string}>}
 */
export async function deleteFace(name) {
    const res = await fetch(`${BACKEND}/api/face/delete`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ name }),
    });
    return handleResponse(res);
}

/**
 * Create a one-time shareable enrollment link (valid 1 hour).
 * @returns {Promise<{url: string, token: string, expires_in: number}>}
 */
export async function createEnrollLink() {
    const res = await fetch(`${BACKEND}/enroll/create`, {
        method: 'POST',
        headers: authHeaders(),
    });
    return handleResponse(res);
}

// ── Share-link (token-based) flows ───────────────────────────────────────────

/**
 * Check whether a share-link token is still valid (no auth needed).
 * @param {string} token
 * @returns {Promise<{valid: boolean, expired: boolean}>}
 */
export async function validateEnrollToken(token) {
    const res = await fetch(`${BACKEND}/api/enroll/${token}/validate`);
    return handleResponse(res);
}

/**
 * Enroll a face using a share-link token (no JWT needed).
 * @param {string} token - the invite token
 * @param {string} name  - person's name
 * @param {string[]} frames - base64 data-URI array
 * @returns {Promise<{status: string, message: string, liveness_score: number, frames_used: number}>}
 */
export async function enrollWithToken(token, name, frames) {
    const res = await fetch(`${BACKEND}/api/enroll/${token}/frames`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, frames }),
    });
    return handleResponse(res);
}

/**
 * Fetch the database of enrolled faces.
 * @returns {Promise<{enrolled: Array}>}
 */
export async function fetchEnrolledFaces() {
    const res = await fetch(`${BACKEND}/api/face/recognition-logs`, {
        headers: authHeaders(),
    });
    return handleResponse(res);
}
