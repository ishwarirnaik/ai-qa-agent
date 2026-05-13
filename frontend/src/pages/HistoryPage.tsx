import React, { useState, useEffect, useMemo, useRef } from 'react';
import { Page, RunStatus, UserSession, StreamEvent, HistoryRun, API_BASE_URL, stageIcon, statusTone, formatStage, formatDate } from '../types';
export function HistoryPage({ history, loading, onRefresh, onSelect }: { history: HistoryRun[]; loading: boolean; onRefresh: () => void; onSelect: (run: HistoryRun) => void }) {
  return (
    <section className="rounded-md border border-outline-variant/10 bg-surface-container p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-widest text-on-surface-variant">Database History</p>
          <h2 className="mt-2 text-2xl font-black">Execution History</h2>
        </div>
        <button className="rounded-md border border-outline-variant/40 px-4 py-2 text-sm font-bold" onClick={onRefresh}>Refresh</button>
      </div>
      {loading ? <p className="text-on-surface-variant">Loading history...</p> : (
        <div className="overflow-hidden rounded-md border border-outline-variant/20">
          <table className="w-full text-left text-sm">
            <thead className="bg-surface-container-high text-[10px] uppercase tracking-widest text-on-surface-variant">
              <tr><th className="p-3">Execution</th><th className="p-3">Target</th><th className="p-3">Status</th><th className="p-3">Created</th><th className="p-3">Report</th></tr>
            </thead>
            <tbody>
              {history.map((run) => (
                <tr className="border-t border-outline-variant/10 hover:bg-surface-container-low" key={run._id}>
                  <td className="p-3 font-mono text-primary"><button onClick={() => onSelect(run)}>{run.execution_id || run._id}</button></td>
                  <td className="max-w-xs truncate p-3">{run.target_url || 'Unknown'}</td>
                  <td className="p-3"><span className={`rounded border px-2 py-1 font-mono text-[10px] ${statusTone(run.status)}`}>{run.status}</span></td>
                  <td className="p-3 text-on-surface-variant">{formatDate(run.created_at)}</td>
                  <td className="p-3">{run.report_url ? <a className="text-primary" href={run.report_url} target="_blank" rel="noreferrer">Open</a> : <span className="text-on-surface-variant">None</span>}</td>
                </tr>
              ))}
              {history.length === 0 && <tr><td className="p-6 text-on-surface-variant" colSpan={5}>No history found for this user.</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

