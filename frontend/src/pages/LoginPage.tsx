import React, { useState, useEffect, useMemo, useRef } from 'react';
import { Page, RunStatus, UserSession, StreamEvent, HistoryRun, API_BASE_URL, stageIcon, statusTone, formatStage, formatDate } from '../types';
export function LoginPage({ onAuth }: { onAuth: (session: UserSession) => void }) {
  const [isSignUp, setIsSignUp] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [message, setMessage] = useState('');

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setMessage('');

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/${isSignUp ? 'signup' : 'login'}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });

      const data = await response.json();
      if (!response.ok) {
        setMessage(data.detail || 'Authentication failed.');
        return;
      }

      onAuth({ userId: data.user_id || email, email, token: data.token });
    } catch {
      setMessage('Backend is not reachable.');
    }
  };

  return (
    <main className="flex min-h-screen items-center justify-center bg-surface p-6 text-on-surface font-body">
      <section className="w-full max-w-md rounded-md border border-outline-variant/40 bg-surface-container p-8 shadow-2xl">
        <div className="mb-8">
          <h1 className="text-[10px] font-black uppercase tracking-widest text-primary">aQa Engine</h1>
          <p className="mt-2 text-3xl font-black tracking-normal">Autonomous QA Hub</p>
          <p className="mt-3 text-sm leading-6 text-on-surface-variant">Sign in, launch real website tests, and keep every execution tied to your account history.</p>
        </div>
        <form className="space-y-5" onSubmit={submit}>
          <input className="w-full rounded-md border border-outline-variant/40 bg-surface-container-low px-4 py-3 font-mono text-sm text-on-surface outline-none focus:border-primary focus:ring-0" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="email@domain.com" type="email" required />
          <input className="w-full rounded-md border border-outline-variant/40 bg-surface-container-low px-4 py-3 font-mono text-sm text-on-surface outline-none focus:border-primary focus:ring-0" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="password" type="password" required />
          {message && <p className="text-xs text-warning">{message}</p>}
          <button className="w-full rounded-md bg-gradient-to-br from-primary to-primary-container py-3 text-sm font-bold text-on-primary transition active:scale-95">
            {isSignUp ? 'Create Account' : 'Sign In'}
          </button>
        </form>
        <button className="mt-5 text-xs font-bold uppercase tracking-widest text-primary-dim hover:text-primary" onClick={() => setIsSignUp(!isSignUp)}>
          {isSignUp ? 'Use existing account' : 'Create a new account'}
        </button>
      </section>
    </main>
  );
}

