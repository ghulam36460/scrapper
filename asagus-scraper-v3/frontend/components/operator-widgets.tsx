import { Clock, ExternalLink, Inbox, Square, Trash2 } from "lucide-react";

import { RecordRow, ScrapeJob } from "../lib/api";
import { JobProgress } from "../lib/page-utils";

export function KeyValueGrid({ rows }: { rows: Array<[string, unknown]> }) {
  return (
    <div className="kv-grid">
      {rows.map(([key, value]) => (
        <div className="mini-metric" key={key}>
          <span>{key}</span>
          <strong>{String(value)}</strong>
        </div>
      ))}
    </div>
  );
}

export function EmptyState({
  title,
  detail,
}: {
  title: string;
  detail: string;
}) {
  return (
    <div className="empty-state">
      <Inbox size={22} />
      <strong>{title}</strong>
      <span>{detail}</span>
    </div>
  );
}

export function JobProgressPanel({
  job,
  progress,
  busy,
  onCancel,
  onDelete,
}: {
  job: ScrapeJob;
  progress: JobProgress;
  busy: boolean;
  onCancel: (jobId: string) => void;
  onDelete: (jobId: string) => void;
}) {
  const canCancel = job.status === "queued" || job.status === "running";
  const canDelete = !canCancel;
  return (
    <section className="panel progress-panel">
      <div className="panel-header">
        <h2>{job.request.query} / {job.request.location}</h2>
        <div className="inline">
          {canCancel ? (
            <button className="btn danger" onClick={() => onCancel(job.id)} disabled={busy}>
              <Square size={15} />
              Stop
            </button>
          ) : null}
          {canDelete ? (
            <button className="btn danger" onClick={() => onDelete(job.id)} disabled={busy}>
              <Trash2 size={15} />
              Delete Job
            </button>
          ) : null}
          <span className={`pill ${job.status === "completed" ? "ok" : job.status === "failed" || job.status === "cancelled" ? "warn" : "info"}`}>{job.status}</span>
        </div>
      </div>
      <div className="progress-track" aria-label="job progress">
        <div className="progress-fill" style={{ width: `${progress.percent}%` }} />
      </div>
      <div className="progress-grid">
        <div className="mini-metric">
          <span>Progress</span>
          <strong>{progress.percent}%</strong>
        </div>
        <div className="mini-metric">
          <span>Pages</span>
          <strong>{job.processed_targets}/{job.total_targets || 0}</strong>
        </div>
        <div className="mini-metric">
          <span>Records</span>
          <strong>{job.records_found}/{job.request.limit}</strong>
        </div>
        <div className="mini-metric">
          <span>Skipped</span>
          <strong>{job.skipped_targets || 0}</strong>
        </div>
        <div className="mini-metric">
          <span>Duplicates</span>
          <strong>{job.duplicate_skips || 0}</strong>
        </div>
        <div className="mini-metric">
          <span>Time</span>
          <strong><Clock size={14} /> {progress.elapsed} / {progress.eta}</strong>
        </div>
      </div>
      <div className="muted progress-message">{job.progress_message || "Waiting"}{job.current_url ? `: ${job.current_url}` : ""}</div>
    </section>
  );
}

export function SocialLinks({ row }: { row: RecordRow }) {
  const links: Array<[string, string | undefined]> = [
    ["FB", row.facebook_url],
    ["IG", row.instagram_url],
    ["X", row.twitter_url],
    ["IN", row.linkedin_url],
  ].filter((item): item is [string, string] => Boolean(item[1]));
  if (!links.length) return <>-</>;
  return (
    <div className="social-links">
      {links.map(([label, href]) => (
        <a href={href} target="_blank" rel="noreferrer" className="pill info" key={`${label}-${href}`}>
          <ExternalLink size={12} />
          {label}
        </a>
      ))}
    </div>
  );
}

export function DecisionMakers({ row }: { row: RecordRow }) {
  const raw = row.raw_fields || {};
  const people = Array.isArray(raw.decision_makers) ? raw.decision_makers.slice(0, 3) : [];
  if (!people.length) return <span className="muted">-</span>;
  return (
    <div className="stack compact-stack">
      {people.map((person, index) => {
        const item = person as Record<string, unknown>;
        const name = String(item.name || "Unknown");
        const title = String(item.title || "Decision maker");
        const url = String(item.profile_url || "");
        return (
          <div key={`${name}-${index}`}>
            {url ? <a href={url} target="_blank" rel="noreferrer">{name}</a> : <strong>{name}</strong>}
            <div className="muted">{title}</div>
          </div>
        );
      })}
    </div>
  );
}

export function OutreachFit({ row }: { row: RecordRow }) {
  const raw = row.raw_fields || {};
  const profileValue = raw.outreach_profile;
  const profile =
    profileValue && typeof profileValue === "object" && !Array.isArray(profileValue)
      ? (profileValue as Record<string, unknown>)
      : {};
  const score = Number(raw.outreach_fit_score ?? profile.score ?? 0);
  const segment = String(raw.outreach_segment ?? profile.segment ?? "");
  const channel = String(raw.recommended_outreach_channel ?? profile.recommended_channel ?? "");
  if (!score && !segment && !channel) return null;
  const tone = score >= 75 ? "ok" : score >= 50 ? "info" : "warn";
  const label = score ? `fit ${Math.round(score)}%` : segment || "fit";
  return (
    <div className="tag-row compact-tags">
      <span className={`pill ${tone}`}>{label}</span>
      {segment ? <span className="pill">{segment}</span> : null}
      {channel ? <span className="pill info">{channel.replaceAll("_", " ")}</span> : null}
    </div>
  );
}

export function RecordTable({ rows, onDelete, busy = false }: { rows: RecordRow[]; onDelete?: (recordId: string) => void; busy?: boolean }) {
  if (!rows.length) {
    return <EmptyState title="No records yet" detail="Run a job or adjust your filters, then refresh this view." />;
  }
  return (
    <div className="table">
      <table>
        <thead>
          <tr>
            <th>Name</th>
            <th>City</th>
            <th>Contact</th>
            <th>Website</th>
            <th>Social</th>
            <th>Owners / CEOs</th>
            <th>Source</th>
            <th>Method</th>
            <th>Quality</th>
            {onDelete ? <th>Actions</th> : null}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>
                <strong>{row.name || "Unnamed"}</strong>
                <div className="muted">{row.category || row.method || "uncategorized"}</div>
              </td>
              <td>{row.city || "-"}</td>
              <td>
                <div>{row.email || "-"}</div>
                <div className="muted">{row.whatsapp || row.phone || "-"}</div>
              </td>
              <td>{row.website_url ? <a className="truncate-link" href={row.website_url} target="_blank" rel="noreferrer">{row.website_url}</a> : "-"}</td>
              <td><SocialLinks row={row} /></td>
              <td><DecisionMakers row={row} /></td>
              <td>{row.source_url ? <a href={row.source_url} target="_blank" rel="noreferrer">source</a> : "-"}</td>
              <td>
                <span className="pill">{row.method || "unknown"}</span>
                <div className="muted">conf {Math.round((row.confidence || 0) * 100)}%</div>
              </td>
              <td>
                <span className="pill info">{Math.round((row.record_completeness || 0) * 100)}%</span>
                {row.duplicate_score ? <span className="pill warn">dup {Math.round(row.duplicate_score * 100)}%</span> : null}
                {row.gdpr_flag ? <span className="pill warn">GDPR</span> : null}
                {row.pdpa_flag ? <span className="pill warn">PDPA</span> : null}
                <OutreachFit row={row} />
              </td>
              {onDelete ? (
                <td>
                  <button className="btn danger compact-btn" type="button" onClick={() => onDelete(row.id)} disabled={busy}>
                    <Trash2 size={13} />
                    Delete
                  </button>
                </td>
              ) : null}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
