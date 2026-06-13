const API_BASE = "/api";

async function request(path, options) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json();
}

export const api = {
  health: () => request("/system/health"),
  dockerStatus: () => request("/system/docker"),

  listCases: () => request("/cases/"),
  getCase: (id) => request(`/cases/${id}`),

  listTemplates: () => request("/templates/"),
  listSweeps: () => request("/sweeps/"),
};
