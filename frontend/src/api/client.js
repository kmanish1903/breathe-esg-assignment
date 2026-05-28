import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://localhost:8000",
  timeout: 30000,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("authToken");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export async function fetchEmissionRecords(filters = {}) {
  const { data } = await api.get("/emission-records/", {
    params: cleanParams(filters),
  });
  return Array.isArray(data) ? data : data.results || [];
}

export async function fetchDataSources(tenant) {
  const { data } = await api.get("/data-sources/", {
    params: cleanParams({ tenant }),
  });
  return Array.isArray(data) ? data : data.results || [];
}

export async function uploadCsv({ tenant, dataSource, normalizer, file }) {
  const formData = new FormData();
  formData.append("tenant", tenant);
  formData.append("data_source", dataSource);
  formData.append("normalizer", normalizer);
  formData.append("file", file);

  const { data } = await api.post("/emission-records/upload-csv/", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

export async function approveEmissionRecord(id, notes = "") {
  const { data } = await api.post(`/emission-records/${id}/approve/`, { notes });
  return data;
}

export async function rejectEmissionRecord(id, rejectionReason) {
  const { data } = await api.post(`/emission-records/${id}/reject/`, {
    rejection_reason: rejectionReason,
  });
  return data;
}

function cleanParams(params) {
  return Object.fromEntries(
    Object.entries(params).filter(([, value]) => value !== "" && value !== undefined),
  );
}

export default api;
