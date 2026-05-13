import React, { useState, useEffect, useMemo, useRef } from 'react';
import { Page, RunStatus, UserSession, StreamEvent, HistoryRun, API_BASE_URL, stageIcon, statusTone, formatStage, formatDate } from '../types';
export function RunDetailPage({ run, onBack }: { run: HistoryRun | null; onBack: () => void }) {
  if (!run) {
    return <button className="text-primary" onClick={onBack}>Back to history</button>;
  }
  return (
    <section className="rounded-md border border-outline-variant/10 bg-surface-container p-6">
      <button className="mb-6 text-sm font-bold text-primary" onClick={onBack}>Back to history</button>
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-2xl font-black">Execution {run.execution_id || run._id}</h2>
        <span className={`rounded border px-2 py-1 font-mono text-[10px] ${statusTone(run.status)}`}>{run.status}</span>
      </div>
      <div className="mt-6 grid gap-5 lg:grid-cols-2">
        <div><p className="text-[10px] uppercase tracking-widest text-on-surface-variant">Target URL</p><p className="mt-2 break-all font-mono text-sm">{run.target_url || 'Unknown'}</p></div>
        <div><p className="text-[10px] uppercase tracking-widest text-on-surface-variant">Created</p><p className="mt-2 text-sm">{formatDate(run.created_at)}</p></div>
        <div className="lg:col-span-2"><p className="text-[10px] uppercase tracking-widest text-on-surface-variant">Prompt</p><p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-on-surface-variant">{run.prompt}</p></div>
        <div className="lg:col-span-2"><p className="text-[10px] uppercase tracking-widest text-on-surface-variant">Result</p><p className="mt-2 max-h-80 overflow-y-auto whitespace-pre-wrap rounded bg-surface-container-low p-4 font-mono text-xs leading-6 text-on-surface-variant">{run.result || 'No result summary stored.'}</p></div>
        {run.test_plan && (
          <div className="lg:col-span-2">
            <p className="text-[10px] uppercase tracking-widest text-on-surface-variant">Test Plan</p>
            <p className="mt-2 max-h-80 overflow-y-auto whitespace-pre-wrap rounded bg-surface-container-low p-4 font-mono text-xs leading-6 text-on-surface-variant">{run.test_plan}</p>
          </div>
        )}
        {run.script_code && (
          <div className="lg:col-span-2">
            <p className="text-[10px] uppercase tracking-widest text-on-surface-variant">Script Code</p>
            <pre className="mt-2 max-h-96 overflow-y-auto whitespace-pre-wrap rounded bg-black/80 text-green-400 p-4 font-mono text-xs leading-6">{run.script_code}</pre>
          </div>
        )}
      </div>
      {run.report_url && <a className="mt-6 inline-flex rounded border border-primary/40 bg-primary/10 px-4 py-2 text-xs font-bold uppercase tracking-widest text-primary" href={run.report_url} target="_blank" rel="noreferrer">Open Unique Report</a>}
    </section>
  );
}

