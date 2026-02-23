const API_BASE = "/api/super-admin";

function getAuthHeaders() {
  const token = localStorage.getItem("authToken") || "";
  return token
    ? { Accept: "application/json", Authorization: `Bearer ${token}` }
    : { Accept: "application/json" };
}

export async function fetchClients() {
  const res = await fetch(`${API_BASE}/clients`, {
    credentials: "include",
    headers: getAuthHeaders(),
  });

  if (!res.ok) {
    throw new Error(`Failed with status ${res.status}`);
  }

  return res.json();
}

export async function createClient(data) {
  const res = await fetch(`${API_BASE}/clients`, {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...getAuthHeaders(),
    },
    body: JSON.stringify(data),
  });

  if (!res.ok) {
    throw new Error(`Failed with status ${res.status}`);
  }

  return res.json();
}
