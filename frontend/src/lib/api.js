const API_BASE = "/api";

async function request(path, options) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body.detail) detail = body.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json();
}

const post = (path, body) =>
  request(path, { method: "POST", body: body ? JSON.stringify(body) : undefined });
const put = (path, body) => request(path, { method: "PUT", body: JSON.stringify(body) });
const del = (path) => request(path, { method: "DELETE" });

export const api = {
  health: () => request("/system/health"),
  dockerStatus: () => request("/system/docker"),
  getSettings: () => request("/system/settings"),
  saveSettings: (values) => put("/system/settings", values),

  // templates
  listTemplates: () => request("/templates/"),
  getTemplate: (id) => request(`/templates/${id}`),

  // cases
  listCases: () => request("/cases/"),
  getCase: (id) => request(`/cases/${id}`),
  createCase: (name, template = "airfoil") => post("/cases/", { name, template }),
  updateSpec: (id, spec) => put(`/cases/${id}/spec`, { spec }),
  generate: (id) => post(`/cases/${id}/generate`),
  meshLog: (id) => request(`/cases/${id}/mesh-log`),
  pipelineStatus: (id) => request(`/cases/${id}/pipeline-status`),
  validate: (id) => request(`/cases/${id}/validate`),
  deleteCase: (id) => del(`/cases/${id}`),

  // geometry / mesh
  naca: (designation, chord = 1.0, n = 120) =>
    post("/geometry/naca", { designation, chord, n }),
  blade: (params) => post("/geometry/blade", params),
  yplus: (velocity, length, fluid, target_yplus) =>
    post("/meshing/yplus", { velocity, length, fluid, target_yplus }),

  // validation overrides
  override: (id, rule_id, message) => post(`/validation/${id}/override`, { rule_id, message }),

  // runs
  startRun: (caseId) => post(`/runs/${caseId}/start`),
  listRuns: (caseId) => request(`/runs/?case_id=${caseId}`),
  latestRun: (caseId) => request(`/runs/latest?case_id=${caseId}`),
  runStatus: (runId) => request(`/runs/${runId}/status`),
  stopRun: (runId) => post(`/runs/${runId}/stop`),
  runSocket: (runId) => {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    return new WebSocket(`${proto}://${location.host}/api/runs/ws/${runId}`);
  },

  // results
  forces: (caseId) => request(`/results/${caseId}/forces`),
  fanPerformance: (caseId) => request(`/results/${caseId}/fan`),
  openParaview: (caseId) => post(`/results/${caseId}/paraview`),
  listFields: (caseId) => request(`/results/${caseId}/fields`),
  fieldSlice: (caseId, name) => request(`/results/${caseId}/field?name=${encodeURIComponent(name)}`),

  // benchmarks
  listBenchmarks: () => request("/benchmarks/"),
  getBenchmark: (id) => request(`/benchmarks/${id}`),

  // sweeps
  listSweeps: () => request("/sweeps/"),
  createSweep: (base_case_id, values, parameter, name) =>
    post("/sweeps/", { base_case_id, values, parameter, name }),
  polar: (sweepId) => request(`/sweeps/${sweepId}/polar`),
  sweepStatus: (sweepId) => request(`/sweeps/${sweepId}/status`),
  runSweep: (sweepId) => post(`/sweeps/${sweepId}/run`),
  stopSweep: (sweepId) => post(`/sweeps/${sweepId}/stop`),
};

// get/set a dotted path inside a spec object (immutably)
export function setSpecPath(spec, dotted, value) {
  const keys = dotted.split(".");
  const next = structuredClone(spec);
  let node = next;
  for (let i = 0; i < keys.length - 1; i++) {
    node[keys[i]] = node[keys[i]] ?? {};
    node = node[keys[i]];
  }
  node[keys[keys.length - 1]] = value;
  return next;
}

export function getSpecPath(spec, dotted) {
  return dotted.split(".").reduce((n, k) => (n == null ? undefined : n[k]), spec);
}
