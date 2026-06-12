const API_BASE = "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
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
  health: () => request<{ status: string; version: string }>("/system/health"),
  dockerStatus: () => request<any>("/system/docker"),

  listCases: () => request<any[]>("/cases/"),
  getCase: (id: string) => request<any>(`/cases/${id}`),

  listTemplates: () => request<any[]>("/templates/"),
  listSweeps: () => request<any[]>("/sweeps/"),
};
