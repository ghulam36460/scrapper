"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import {
  Upload, FileText, Trash2, Eye, Users, X, Check,
  AlertCircle, Loader2, ChevronRight, Download, Database
} from "lucide-react";
import { leadsApi } from "@/lib/api";
import Modal from "@/components/Modal";

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    pending: "badge-gray",
    sent: "badge-blue",
    replied: "badge-green",
    bounced: "badge-red",
    unsubscribed: "badge-yellow",
    skipped: "badge-gray",
  };
  return <span className={`badge ${map[status] || "badge-gray"}`}>{status}</span>;
}

function FileStatsRow({ file }: { file: any }) {
  const [stats, setStats] = useState<any>(null);
  const [expanded, setExpanded] = useState(false);
  const [leads, setLeads] = useState<any[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(0);
  const [loadingLeads, setLoadingLeads] = useState(false);

  const loadStats = useCallback(async () => {
    const res = await leadsApi.getFileStats(file.id);
    setStats(res.data);
  }, [file.id]);

  const loadLeads = useCallback(async (p: number) => {
    setLoadingLeads(true);
    try {
      const res = await leadsApi.getFileLeads(file.id, p, 20);
      setLeads(res.data.items);
      setTotalPages(res.data.pages);
      setPage(p);
    } finally {
      setLoadingLeads(false);
    }
  }, [file.id]);

  useEffect(() => { loadStats(); }, [loadStats]);

  const toggleExpand = () => {
    if (!expanded) {
      setExpanded(true);
      loadLeads(1);
    } else {
      setExpanded(false);
    }
  };

  const available = stats ? stats.available : "—";
  const pct = stats && stats.total > 0 ? Math.round((stats.sent / stats.total) * 100) : 0;

  return (
    <div className="border border-gray-100 rounded-xl overflow-hidden">
      {/* File Header */}
      <div
        className="flex items-center gap-4 p-4 bg-white hover:bg-gray-50 cursor-pointer transition-colors"
        onClick={toggleExpand}
      >
        <div className="w-9 h-9 rounded-lg bg-indigo-50 flex items-center justify-center shrink-0">
          <FileText size={16} className="text-indigo-600" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-medium text-gray-800 truncate">{file.original_name}</p>
          <p className="text-xs text-gray-400 mt-0.5">
            {new Date(file.uploaded_at).toLocaleDateString()} · {file.valid_leads} valid leads
          </p>
        </div>
        <div className="hidden md:flex items-center gap-6 text-xs text-gray-600">
          <div className="text-center">
            <div className="font-bold text-gray-900">{file.total_leads}</div>
            <div className="text-gray-400">Total</div>
          </div>
          <div className="text-center">
            <div className="font-bold text-emerald-600">{available}</div>
            <div className="text-gray-400">Available</div>
          </div>
          {stats && (
            <>
              <div className="text-center">
                <div className="font-bold text-blue-600">{stats.sent}</div>
                <div className="text-gray-400">Sent</div>
              </div>
              <div className="text-center">
                <div className="font-bold text-green-600">{stats.replied}</div>
                <div className="text-gray-400">Replied</div>
              </div>
            </>
          )}
        </div>
        <div className="w-24 hidden lg:block">
          <div className="progress-bar-bg">
            <div className="progress-bar-fill" style={{ width: `${pct}%` }} />
          </div>
          <p className="text-xs text-gray-400 mt-1 text-right">{pct}% sent</p>
        </div>
        <ChevronRight
          size={16}
          className={`text-gray-400 transition-transform ${expanded ? "rotate-90" : ""}`}
        />
      </div>

      {/* Expanded Leads Table */}
      {expanded && (
        <div className="border-t border-gray-100">
          {loadingLeads ? (
            <div className="flex justify-center py-8">
              <Loader2 size={20} className="animate-spin text-indigo-600" />
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr>
                      {["Name", "Business", "Email", "Phone", "Status"].map(h => (
                        <th key={h} className="table-header">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {leads.map((l) => (
                      <tr key={l.id} className="hover:bg-gray-50">
                        <td className="table-cell font-medium">{l.name || "—"}</td>
                        <td className="table-cell text-gray-500">{l.business_name || "—"}</td>
                        <td className="table-cell text-indigo-600">{l.email}</td>
                        <td className="table-cell text-gray-500">{l.phone || "—"}</td>
                        <td className="table-cell"><StatusBadge status={l.status} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex justify-center gap-2 p-3 border-t border-gray-50">
                  <button
                    onClick={() => loadLeads(page - 1)}
                    disabled={page === 1}
                    className="btn-secondary py-1 px-3 text-xs disabled:opacity-40"
                  >
                    Prev
                  </button>
                  <span className="text-xs text-gray-500 py-1.5 px-2">
                    Page {page} of {totalPages}
                  </span>
                  <button
                    onClick={() => loadLeads(page + 1)}
                    disabled={page === totalPages}
                    className="btn-secondary py-1 px-3 text-xs disabled:opacity-40"
                  >
                    Next
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

function ColumnMappingModal({
  uploadResult, onConfirm, onCancel,
}: {
  uploadResult: any;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const [mapping, setMapping] = useState<any>({
    email_col: uploadResult.auto_mapping?.email || "",
    name_col: uploadResult.auto_mapping?.name || "",
    business_col: uploadResult.auto_mapping?.business || "",
    phone_col: uploadResult.auto_mapping?.phone || "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<any>(null);

  const handleConfirm = async () => {
    if (!mapping.email_col) {
      setError("Email column is required.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const res = await leadsApi.confirmUpload({
        temp_filename: uploadResult.temp_filename,
        original_name: uploadResult.original_name,
        email_col: mapping.email_col,
        name_col: mapping.name_col || undefined,
        business_col: mapping.business_col || undefined,
        phone_col: mapping.phone_col || undefined,
      });
      setResult(res.data);
    } catch (e: any) {
      setError(e.response?.data?.detail || "Failed to import leads.");
    } finally {
      setSaving(false);
    }
  };

  const cols = ["", ...uploadResult.columns];

  return (
    <Modal onClose={onCancel}>
      <div className="modal-box" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="text-lg font-semibold text-gray-900">Map CSV Columns</h2>
          <button onClick={onCancel} className="p-1.5 hover:bg-gray-100 rounded-lg">
            <X size={16} />
          </button>
        </div>
        <div className="modal-body">
          {error && <div className="alert-error">{error}</div>}

          {result ? (
            <div className="space-y-3">
              <div className="alert-success flex items-center gap-2">
                <Check size={16} /> Leads imported successfully!
              </div>
              <div className="grid grid-cols-2 gap-3 text-sm">
                {[
                  { label: "Total rows", value: result.total, color: "text-gray-800" },
                  { label: "Valid leads", value: result.valid, color: "text-emerald-600" },
                  { label: "Invalid emails", value: result.invalid, color: "text-red-600" },
                  { label: "Duplicates (in file)", value: result.duplicates_in_file, color: "text-amber-600" },
                  { label: "Already emailed globally", value: result.already_sent_globally, color: "text-blue-600" },
                ].map(stat => (
                  <div key={stat.label} className="flex justify-between p-3 bg-gray-50 rounded-lg">
                    <span className="text-gray-500">{stat.label}</span>
                    <span className={`font-bold ${stat.color}`}>{stat.value}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <>
              {/* Preview table */}
              <div className="overflow-x-auto border border-gray-100 rounded-lg">
                <table className="w-full text-xs">
                  <thead>
                    <tr>
                      {uploadResult.columns.map((c: string) => (
                        <th key={c} className="table-header py-2 px-3">{c}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {uploadResult.preview.slice(0, 3).map((row: any, i: number) => (
                      <tr key={i}>
                        {uploadResult.columns.map((c: string) => (
                          <td key={c} className="table-cell py-1.5 px-3">{row[c] || "—"}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Column mapping */}
              <div className="grid grid-cols-2 gap-3">
                {[
                  { key: "email_col", label: "Email Column *", required: true },
                  { key: "name_col", label: "Name Column" },
                  { key: "business_col", label: "Business Column" },
                  { key: "phone_col", label: "Phone Column" },
                ].map(({ key, label }) => (
                  <div key={key} className="form-group">
                    <label className="label">{label}</label>
                    <select
                      className="select"
                      value={mapping[key]}
                      onChange={e => setMapping((m: any) => ({ ...m, [key]: e.target.value }))}
                    >
                      {cols.map((c: string) => (
                        <option key={c} value={c}>{c || "— Skip —"}</option>
                      ))}
                    </select>
                  </div>
                ))}
              </div>
              <p className="text-xs text-gray-400">
                Total rows in file: <strong>{uploadResult.total_rows}</strong>
              </p>
            </>
          )}
        </div>
        <div className="modal-footer">
          {result ? (
            <button onClick={onConfirm} className="btn-primary">
              <Check size={14} /> Done
            </button>
          ) : (
            <>
              <button onClick={onCancel} className="btn-secondary">Cancel</button>
              <button onClick={handleConfirm} disabled={saving || !mapping.email_col} className="btn-primary">
                {saving ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
                Import Leads
              </button>
            </>
          )}
        </div>
      </div>
    </Modal>
  );
}

export default function LeadsPage() {
  const [files, setFiles] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [uploadResult, setUploadResult] = useState<any>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchFiles = useCallback(async () => {
    try {
      const res = await leadsApi.listFiles();
      setFiles(res.data);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchFiles(); }, [fetchFiles]);

  const handleFile = async (file: File) => {
    if (!file.name.endsWith(".csv")) {
      setUploadError("Please upload a CSV file.");
      return;
    }
    setUploading(true);
    setUploadError("");
    try {
      const res = await leadsApi.uploadCsv(file);
      setUploadResult(res.data);
    } catch (e: any) {
      setUploadError(e.response?.data?.detail || "Upload failed. Please try again.");
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  const handleDeleteFile = async (fileId: number) => {
    if (!confirm("Delete this lead file and all its leads?")) return;
    try {
      await leadsApi.deleteFile(fileId);
      fetchFiles();
    } catch (e: any) {
      alert(e.response?.data?.detail || "Failed to delete file.");
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">Lead Files</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {files.length} file{files.length !== 1 ? "s" : ""} · Upload CSV to import leads
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-gray-400">
          <Database size={13} />
          <span>3-level deduplication</span>
        </div>
      </div>

      {/* Upload Zone */}
      <div
        onClick={() => !uploading && fileInputRef.current?.click()}
        onDragOver={e => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={`
          border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-all duration-200
          ${dragging
            ? "border-indigo-500 bg-indigo-50"
            : "border-gray-200 bg-white hover:border-indigo-300 hover:bg-indigo-50/30"
          }
        `}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv"
          className="hidden"
          onChange={e => e.target.files?.[0] && handleFile(e.target.files[0])}
        />
        {uploading ? (
          <div className="flex flex-col items-center gap-3">
            <Loader2 size={28} className="animate-spin text-indigo-600" />
            <p className="text-sm font-medium text-indigo-700">Parsing CSV...</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-indigo-100 flex items-center justify-center">
              <Upload size={22} className="text-indigo-600" />
            </div>
            <div>
              <p className="text-sm font-semibold text-gray-700">
                Drop your CSV here, or <span className="text-indigo-600">browse</span>
              </p>
              <p className="text-xs text-gray-400 mt-1">
                Supports CSV files with email, name, business, phone columns
              </p>
            </div>
          </div>
        )}
      </div>

      {uploadError && <div className="alert-error flex items-center gap-2">
        <AlertCircle size={15} /> {uploadError}
      </div>}

      {/* Lead Files List */}
      <div>
        <div className="flex items-center justify-between mb-3">
          <h2 className="section-title mb-0">Uploaded Files ({files.length})</h2>
        </div>

        {loading ? (
          <div className="flex justify-center py-12">
            <Loader2 size={24} className="animate-spin text-indigo-600" />
          </div>
        ) : files.length === 0 ? (
          <div className="card text-center py-12">
            <Users size={32} className="mx-auto mb-3 text-gray-200" />
            <p className="text-sm text-gray-500">No lead files uploaded yet</p>
          </div>
        ) : (
          <div className="space-y-3">
            {files.map((f) => (
              <div key={f.id} className="relative group">
                <FileStatsRow file={f} />
                <button
                  onClick={() => handleDeleteFile(f.id)}
                  className="absolute top-3 right-12 opacity-0 group-hover:opacity-100 p-1.5 hover:bg-red-50 rounded-lg text-red-400 hover:text-red-600 transition-all"
                  title="Delete file"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Column Mapping Modal */}
      {uploadResult && (
        <ColumnMappingModal
          uploadResult={uploadResult}
          onCancel={() => setUploadResult(null)}
          onConfirm={() => {
            setUploadResult(null);
            fetchFiles();
          }}
        />
      )}
    </div>
  );
}
