import React, { useState, useEffect } from 'react';
import { Page, RunStatus, UserSession, HistoryRun, API_BASE_URL } from './types';
import { Shell } from './components/Shell';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import { NewRunPage } from './pages/NewRunPage';
import { HistoryPage } from './pages/HistoryPage';
import { RunDetailPage } from './pages/RunDetailPage';
export default function App() {
  const [session, setSession] = useState<UserSession | null>(() => {
    const stored = localStorage.getItem('aqa_session');
    return stored ? JSON.parse(stored) : null;
  });
  const [page, setPage] = useState<Page>(session ? 'dashboard' : 'login');
  const [history, setHistory] = useState<HistoryRun[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [selectedRun, setSelectedRun] = useState<HistoryRun | null>(null);
  const [globalStatus, setGlobalStatus] = useState<RunStatus>('READY');

  const loadHistory = async (userId = session?.userId) => {
    if (!userId) return;
    setHistoryLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/history`, {
        headers: {
          'Authorization': `Bearer ${session?.token}`
        }
      });
      const data = await response.json();
      setHistory(data);
    } finally {
      setHistoryLoading(false);
    }
  };

  useEffect(() => {
    if (session) loadHistory(session.userId);
  }, [session]);

  const handleAuth = (nextSession: UserSession) => {
    localStorage.setItem('aqa_session', JSON.stringify(nextSession));
    setSession(nextSession);
    setPage('dashboard');
  };

  const logout = () => {
    localStorage.removeItem('aqa_session');
    setSession(null);
    setPage('login');
    setHistory([]);
  };

  if (!session || page === 'login') {
    return <LoginPage onAuth={handleAuth} />;
  }

  return (
    <Shell page={page} session={session} status={globalStatus} onNavigate={setPage} onLogout={logout}>
      {page === 'dashboard' && <DashboardPage history={history} onNavigate={setPage} />}
      {page === 'new-run' && <NewRunPage session={session} onStatusChange={setGlobalStatus} onComplete={() => { loadHistory(session.userId); }} />}
      {page === 'history' && <HistoryPage history={history} loading={historyLoading} onRefresh={() => loadHistory(session.userId)} onSelect={(run) => { setSelectedRun(run); setPage('run-detail'); }} />}
      {page === 'run-detail' && <RunDetailPage run={selectedRun} onBack={() => setPage('history')} />}
    </Shell>
  );
}
