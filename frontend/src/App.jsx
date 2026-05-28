import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Check,
  Eye,
  FileUp,
  Filter,
  Loader2,
  RefreshCw,
  Search,
  X,
} from "lucide-react";

import {
  approveEmissionRecord,
  fetchDataSources,
  fetchEmissionRecords,
  rejectEmissionRecord,
  uploadCsv,
} from "./api/client";

const STATUS_OPTIONS = [
  { value: "", label: "All statuses" },
  { value: "draft", label: "Draft" },
  { value: "pending_review", label: "Pending review" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
];

const NORMALIZERS = [
  { value: "utility", label: "Utility" },
  { value: "sap", label: "SAP" },
  { value: "travel", label: "Travel" },
];

export default function App() {
  const [tenantId, setTenantId] = useState("");
  const [records, setRecords] = useState([]);
  const [sources, setSources] = useState([]);
  const [filters, setFilters] = useState({
    data_source: "",
    approval_status: "",
    flagged: "",
  });
  const [selectedRecord, setSelectedRecord] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const loadRecords = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      const data = await fetchEmissionRecords({
        tenant: tenantId,
        ...filters,
      });
      setRecords(data);
    } catch (requestError) {
      setError(apiError(requestError));
    } finally {
      setIsLoading(false);
    }
  }, [filters, tenantId]);

  useEffect(() => {
    loadRecords();
  }, [loadRecords]);

  useEffect(() => {
    if (!tenantId) {
      setSources([]);
      return;
    }
    fetchDataSources(tenantId)
      .then(setSources)
      .catch((requestError) => setError(apiError(requestError)));
  }, [tenantId]);

  const metrics = useMemo(() => {
    const flagged = records.filter((record) => record.is_suspicious).length;
    const pending = records.filter(
      (record) => record.approval_status === "draft" || record.approval_status === "pending_review",
    ).length;
    const approved = records.filter((record) => record.approval_status === "approved").length;
    return { total: records.length, flagged, pending, approved };
  }, [records]);

  async function handleUpload(payload) {
    setMessage("");
    setError("");
    try {
      const result = await uploadCsv(payload);
      setMessage(`Uploaded ${result.created_records} normalized records.`);
      await loadRecords();
    } catch (requestError) {
      setError(apiError(requestError));
    }
  }

  async function handleApprove(record) {
    setError("");
    try {
      const updated = await approveEmissionRecord(record.id);
      setRecords((current) => replaceRecord(current, updated));
      setMessage("Record approved and locked.");
    } catch (requestError) {
      setError(apiError(requestError));
    }
  }

  async function handleReject(record) {
    const reason = window.prompt("Rejection reason");
    if (!reason) return;

    setError("");
    try {
      const updated = await rejectEmissionRecord(record.id, reason);
      setRecords((current) => replaceRecord(current, updated));
      setMessage("Record rejected.");
    } catch (requestError) {
      setError(apiError(requestError));
    }
  }

  return (
    <main className="min-h-screen">
      <section className="border-b border-line bg-white">
        <div className="mx-auto flex max-w-7xl flex-col gap-5 px-4 py-5 sm:px-6 lg:px-8">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-moss">
                Analyst review
              </p>
              <h1 className="mt-1 text-2xl font-semibold text-ink">ESG emissions dashboard</h1>
            </div>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              <Metric label="Total" value={metrics.total} />
              <Metric label="Flagged" value={metrics.flagged} intent="warning" />
              <Metric label="Pending" value={metrics.pending} />
              <Metric label="Approved" value={metrics.approved} intent="success" />
            </div>
          </div>
          <TenantInput value={tenantId} onChange={setTenantId} />
        </div>
      </section>

      <section className="mx-auto grid max-w-7xl gap-5 px-4 py-5 sm:px-6 lg:grid-cols-[360px_minmax(0,1fr)] lg:px-8">
        <UploadPanel tenantId={tenantId} sources={sources} onUpload={handleUpload} />

        <div className="min-w-0 space-y-4">
          <StatusMessage error={error} message={message} />
          <FilterBar
            filters={filters}
            sources={sources}
            onChange={setFilters}
            onRefresh={loadRecords}
            isLoading={isLoading}
          />
          <EmissionTable
            records={records}
            isLoading={isLoading}
            onInspect={setSelectedRecord}
            onApprove={handleApprove}
            onReject={handleReject}
          />
        </div>
      </section>

      <InspectModal record={selectedRecord} onClose={() => setSelectedRecord(null)} />
    </main>
  );
}

function TenantInput({ value, onChange }) {
  return (
    <label className="flex max-w-xl flex-col gap-1 text-sm font-medium text-ink">
      Tenant ID
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink/45" />
        <input
          value={value}
          onChange={(event) => onChange(event.target.value)}
          className="h-10 w-full rounded-md border border-line bg-panel pl-9 pr-3 text-sm"
          placeholder="Paste tenant UUID"
        />
      </div>
    </label>
  );
}

function Metric({ label, value, intent = "neutral" }) {
  const tone = {
    neutral: "border-line bg-panel text-ink",
    warning: "border-amber/30 bg-amber/10 text-amber",
    success: "border-moss/30 bg-moss/10 text-moss",
  }[intent];

  return (
    <div className={`min-w-24 rounded-md border px-3 py-2 ${tone}`}>
      <div className="text-xs font-medium">{label}</div>
      <div className="text-xl font-semibold leading-6">{value}</div>
    </div>
  );
}

function UploadPanel({ tenantId, sources, onUpload }) {
  const [dataSource, setDataSource] = useState("");
  const [normalizer, setNormalizer] = useState("utility");
  const [file, setFile] = useState(null);
  const [isUploading, setIsUploading] = useState(false);

  async function submit(event) {
    event.preventDefault();
    if (!tenantId || !dataSource || !file) return;

    setIsUploading(true);
    try {
      await onUpload({ tenant: tenantId, dataSource, normalizer, file });
      setFile(null);
      event.currentTarget.reset();
    } finally {
      setIsUploading(false);
    }
  }

  return (
    <form onSubmit={submit} className="h-fit rounded-md border border-line bg-white p-4 shadow-soft">
      <div className="mb-4 flex items-center gap-2">
        <FileUp className="h-5 w-5 text-moss" />
        <h2 className="text-base font-semibold">Upload CSV</h2>
      </div>

      <div className="space-y-3">
        <Field label="Data source">
          <select
            value={dataSource}
            onChange={(event) => setDataSource(event.target.value)}
            className="h-10 w-full rounded-md border border-line bg-white px-3 text-sm"
          >
            <option value="">Select source</option>
            {sources.map((source) => (
              <option key={source.id} value={source.id}>
                {source.name}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Normalizer">
          <select
            value={normalizer}
            onChange={(event) => setNormalizer(event.target.value)}
            className="h-10 w-full rounded-md border border-line bg-white px-3 text-sm"
          >
            {NORMALIZERS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </Field>

        <Field label="CSV file">
          <input
            type="file"
            accept=".csv,text/csv"
            onChange={(event) => setFile(event.target.files?.[0] || null)}
            className="block w-full rounded-md border border-line bg-white px-3 py-2 text-sm file:mr-3 file:rounded-md file:border-0 file:bg-moss file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-white"
          />
        </Field>

        <button
          type="submit"
          disabled={!tenantId || !dataSource || !file || isUploading}
          className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-md bg-moss px-4 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-ink/25"
        >
          {isUploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileUp className="h-4 w-4" />}
          Upload
        </button>
      </div>
    </form>
  );
}

function Field({ label, children }) {
  return (
    <label className="block text-sm font-medium text-ink">
      <span className="mb-1 block">{label}</span>
      {children}
    </label>
  );
}

function FilterBar({ filters, sources, onChange, onRefresh, isLoading }) {
  function update(key, value) {
    onChange((current) => ({ ...current, [key]: value }));
  }

  return (
    <div className="flex flex-col gap-3 rounded-md border border-line bg-white p-3 sm:flex-row sm:items-center">
      <div className="flex items-center gap-2 text-sm font-semibold text-ink">
        <Filter className="h-4 w-4 text-moss" />
        Filters
      </div>
      <select
        value={filters.data_source}
        onChange={(event) => update("data_source", event.target.value)}
        className="h-9 rounded-md border border-line bg-white px-3 text-sm"
      >
        <option value="">All sources</option>
        {sources.map((source) => (
          <option key={source.id} value={source.id}>
            {source.name}
          </option>
        ))}
      </select>
      <select
        value={filters.approval_status}
        onChange={(event) => update("approval_status", event.target.value)}
        className="h-9 rounded-md border border-line bg-white px-3 text-sm"
      >
        {STATUS_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <select
        value={filters.flagged}
        onChange={(event) => update("flagged", event.target.value)}
        className="h-9 rounded-md border border-line bg-white px-3 text-sm"
      >
        <option value="">All records</option>
        <option value="true">Flagged only</option>
        <option value="false">Not flagged</option>
      </select>
      <button
        type="button"
        onClick={onRefresh}
        className="inline-flex h-9 items-center justify-center gap-2 rounded-md border border-line px-3 text-sm font-medium"
      >
        <RefreshCw className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} />
        Refresh
      </button>
    </div>
  );
}

function EmissionTable({ records, isLoading, onInspect, onApprove, onReject }) {
  return (
    <div className="overflow-hidden rounded-md border border-line bg-white shadow-soft">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-line text-sm">
          <thead className="bg-panel">
            <tr className="text-left text-xs font-semibold uppercase text-ink/65">
              <th className="px-3 py-3">Source</th>
              <th className="px-3 py-3">Scope</th>
              <th className="px-3 py-3">Period</th>
              <th className="px-3 py-3 text-right">CO2e kg</th>
              <th className="px-3 py-3">Status</th>
              <th className="px-3 py-3">Flags</th>
              <th className="px-3 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {isLoading && (
              <tr>
                <td colSpan="7" className="px-3 py-10 text-center text-ink/60">
                  Loading records...
                </td>
              </tr>
            )}
            {!isLoading && records.length === 0 && (
              <tr>
                <td colSpan="7" className="px-3 py-10 text-center text-ink/60">
                  No records found.
                </td>
              </tr>
            )}
            {!isLoading &&
              records.map((record) => (
                <tr
                  key={record.id}
                  className={record.is_suspicious ? "bg-amber/10" : "bg-white"}
                >
                  <td className="max-w-52 px-3 py-3">
                    <div className="truncate font-medium">{record.data_source_name || record.data_source}</div>
                    <div className="truncate text-xs text-ink/55">{record.source_record_id || record.id}</div>
                  </td>
                  <td className="px-3 py-3">{labelize(record.scope)}</td>
                  <td className="whitespace-nowrap px-3 py-3">
                    {record.period_start} to {record.period_end}
                  </td>
                  <td className="px-3 py-3 text-right font-medium">{Number(record.co2e_kg).toLocaleString()}</td>
                  <td className="px-3 py-3">
                    <StatusPill status={record.approval_status} />
                  </td>
                  <td className="px-3 py-3">
                    {record.is_suspicious ? (
                      <span className="inline-flex items-center gap-1 rounded-md border border-amber/30 bg-amber/10 px-2 py-1 text-xs font-medium text-amber">
                        <AlertTriangle className="h-3.5 w-3.5" />
                        {record.suspicious_flags?.length || 1}
                      </span>
                    ) : (
                      <span className="text-xs text-ink/45">Clear</span>
                    )}
                  </td>
                  <td className="px-3 py-3">
                    <div className="flex justify-end gap-1.5">
                      <IconButton title="Inspect" onClick={() => onInspect(record)}>
                        <Eye className="h-4 w-4" />
                      </IconButton>
                      <IconButton
                        title="Approve"
                        disabled={record.is_locked || record.approval_status === "approved"}
                        onClick={() => onApprove(record)}
                      >
                        <Check className="h-4 w-4" />
                      </IconButton>
                      <IconButton
                        title="Reject"
                        disabled={record.is_locked || record.approval_status === "rejected"}
                        onClick={() => onReject(record)}
                      >
                        <X className="h-4 w-4" />
                      </IconButton>
                    </div>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function StatusPill({ status }) {
  const styles = {
    approved: "border-moss/30 bg-moss/10 text-moss",
    rejected: "border-coral/30 bg-coral/10 text-coral",
    pending_review: "border-amber/30 bg-amber/10 text-amber",
    draft: "border-line bg-panel text-ink/70",
  };
  return (
    <span className={`inline-flex rounded-md border px-2 py-1 text-xs font-medium ${styles[status] || styles.draft}`}>
      {labelize(status)}
    </span>
  );
}

function IconButton({ title, children, disabled, onClick }) {
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      disabled={disabled}
      onClick={onClick}
      className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-line bg-white text-ink hover:bg-panel disabled:cursor-not-allowed disabled:opacity-35"
    >
      {children}
    </button>
  );
}

function InspectModal({ record, onClose }) {
  if (!record) return null;

  const rawData = record.metadata?.source_row || {};
  const normalized = {
    scope: record.scope,
    category: record.category,
    activity_type: record.activity_type,
    activity_value: record.activity_value,
    activity_unit: record.activity_unit,
    normalized_value: record.normalized_value,
    normalized_unit: record.normalized_unit,
    co2e_kg: record.co2e_kg,
    period_start: record.period_start,
    period_end: record.period_end,
    suspicious_flags: record.suspicious_flags,
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/45 p-4">
      <div className="max-h-[90vh] w-full max-w-5xl overflow-hidden rounded-md bg-white shadow-soft">
        <div className="flex items-center justify-between border-b border-line px-4 py-3">
          <div>
            <h2 className="text-base font-semibold">Record inspection</h2>
            <p className="text-xs text-ink/55">{record.id}</p>
          </div>
          <IconButton title="Close" onClick={onClose}>
            <X className="h-4 w-4" />
          </IconButton>
        </div>

        <div className="grid max-h-[72vh] gap-4 overflow-y-auto p-4 lg:grid-cols-2">
          <DataBlock title="Raw CSV row" data={rawData} />
          <DataBlock title="Normalized record" data={normalized} />
        </div>
      </div>
    </div>
  );
}

function DataBlock({ title, data }) {
  return (
    <section>
      <h3 className="mb-2 text-sm font-semibold">{title}</h3>
      <pre className="max-h-[58vh] overflow-auto rounded-md border border-line bg-panel p-3 text-xs leading-5 text-ink">
        {JSON.stringify(data, null, 2)}
      </pre>
    </section>
  );
}

function StatusMessage({ error, message }) {
  if (!error && !message) return null;
  return (
    <div
      className={`rounded-md border px-3 py-2 text-sm ${
        error ? "border-coral/30 bg-coral/10 text-coral" : "border-moss/30 bg-moss/10 text-moss"
      }`}
    >
      {error || message}
    </div>
  );
}

function replaceRecord(records, updatedRecord) {
  return records.map((record) => (record.id === updatedRecord.id ? updatedRecord : record));
}

function labelize(value = "") {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function apiError(error) {
  const data = error.response?.data;
  if (!data) return error.message || "Request failed.";
  if (typeof data === "string") return data;
  return JSON.stringify(data);
}
