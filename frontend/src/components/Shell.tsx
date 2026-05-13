import React, { useState, useEffect, useMemo, useRef } from 'react';
import { Page, RunStatus, UserSession, StreamEvent, HistoryRun, API_BASE_URL, stageIcon, statusTone, formatStage, formatDate } from '../types';
export function Shell({
  page,
  session,
  status,
  onNavigate,
  onLogout,
  children,
}: {
  page: Page;
  session: UserSession;
  status: RunStatus;
  onNavigate: (page: Page) => void;
  onLogout: () => void;
  children: React.ReactNode;
}) {
  const navItem = (target: Page, icon: string, label: string) => (
    <button
      className={`flex w-full items-center gap-x-3 rounded-md p-3 text-left text-sm font-medium transition-all ${
        page === target ? 'translate-x-1 border-r-2 border-primary bg-surface-container-high text-primary' : 'text-on-surface-variant hover:bg-surface-container hover:text-on-surface'
      }`}
      onClick={() => onNavigate(target)}
    >
      <span className="material-symbols-outlined">{icon}</span>
      {label}
    </button>
  );

  return (
    <div className="h-screen overflow-hidden bg-surface text-on-surface font-body">
      <aside className="fixed left-0 top-0 z-50 flex h-full w-64 flex-col gap-y-2 bg-surface-container-low p-4">
        <div className="mb-8 px-2">
          <h1 className="text-[10px] font-black uppercase tracking-widest text-on-surface">aQa Engine</h1>
          <p className="text-[10px] text-on-surface-variant opacity-70">{session.email}</p>
        </div>

        <nav className="flex flex-1 flex-col gap-y-1">
          {navItem('dashboard', 'dashboard', 'Dashboard')}
          {navItem('new-run', 'add_circle', 'New Test Run')}
          {navItem('history', 'history', 'Execution History')}
        </nav>

        <div className="mt-auto flex flex-col gap-y-1 border-t border-outline-variant/20 pt-4">
          <button className="mb-4 rounded-md bg-gradient-to-br from-primary to-primary-container py-2.5 text-sm font-bold text-on-primary transition-transform active:scale-95" onClick={() => onNavigate('new-run')}>
            Launch Agent
          </button>
          <button className="flex items-center gap-x-3 p-2 text-xs text-on-surface-variant transition-colors hover:text-primary" onClick={onLogout}>
            <span className="material-symbols-outlined text-sm">logout</span>
            Sign Out
          </button>
        </div>
      </aside>

      <main className="ml-64 flex h-screen flex-col">
        <header className="fixed left-64 right-0 top-0 z-40 flex h-16 items-center justify-between border-b border-outline-variant/20 bg-black/80 px-6 backdrop-blur-xl">
          <div className="flex items-center gap-x-4">
            <span className="text-xl font-bold tracking-normal text-on-surface">Execution Hub</span>
            <div className="h-4 w-px bg-outline-variant/40" />
            <div className={`flex items-center gap-x-2 rounded border px-2 py-1 font-mono text-[10px] ${statusTone(status)}`}>
              <span className={`h-1.5 w-1.5 rounded-full ${status === 'RUNNING' ? 'animate-pulse bg-primary' : 'bg-current'}`} />
              {status}
            </div>
          </div>
          <div className="flex items-center gap-x-4 text-on-surface-variant">
            <button className="transition hover:text-primary" onClick={() => onNavigate('history')}>
              <span className="material-symbols-outlined">manage_search</span>
            </button>
            <span className="material-symbols-outlined">account_circle</span>
          </div>
        </header>

        <div className="custom-scrollbar mt-16 flex-1 overflow-y-auto bg-surface-container-lowest p-8">{children}</div>
      </main>
    </div>
  );
}

