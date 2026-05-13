import React, { useState, useEffect, useMemo, useRef } from 'react';
import { Page, RunStatus, UserSession, StreamEvent, HistoryRun, API_BASE_URL, stageIcon, statusTone, formatStage, formatDate } from '../types';
export function DashboardPage({ onNavigate, history }: { onNavigate: (page: Page) => void; history: HistoryRun[] }) {
  const latest = history[0];
  return (
    <div className="grid grid-cols-12 gap-6">
      <section className="col-span-12 rounded-md border border-outline-variant/10 bg-surface-container p-6 lg:col-span-7">
        <p className="font-mono text-[10px] uppercase tracking-widest text-on-surface-variant">Start</p>
        <h2 className="mt-3 text-3xl font-black">What do you want to test?</h2>
        <p className="mt-3 max-w-2xl text-sm leading-6 text-on-surface-variant">Create a fresh real-site execution or inspect previous runs associated with this account. Every run receives a unique execution id and its own report path.</p>
        <div className="mt-8 flex flex-wrap gap-3">
          <button className="rounded-md bg-gradient-to-br from-primary to-primary-container px-5 py-3 text-sm font-bold text-on-primary" onClick={() => onNavigate('new-run')}>New Test Run</button>
          <button className="rounded-md border border-outline-variant/40 bg-surface-container-low px-5 py-3 text-sm font-bold text-on-surface" onClick={() => onNavigate('history')}>View History</button>
        </div>
      </section>

      <section className="col-span-12 rounded-md border border-outline-variant/10 bg-surface-container-low p-6 lg:col-span-5">
        <p className="font-mono text-[10px] uppercase tracking-widest text-on-surface-variant">Latest Execution</p>
        {latest ? (
          <div className="mt-5 space-y-3">
            <div className={`inline-flex rounded border px-2 py-1 font-mono text-[10px] ${statusTone(latest.status)}`}>{latest.status}</div>
            <h3 className="break-all text-lg font-bold">{latest.target_url || 'Unknown target'}</h3>
            <p className="line-clamp-3 text-sm leading-6 text-on-surface-variant">{latest.prompt}</p>
            <button className="text-sm font-bold text-primary" onClick={() => onNavigate('history')}>Open in history</button>
          </div>
        ) : (
          <p className="mt-5 text-sm text-on-surface-variant">No executions yet.</p>
        )}
      </section>
    </div>
  );
}

