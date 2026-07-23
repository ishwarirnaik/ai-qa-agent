import React, { useState, useEffect, useMemo, useRef } from 'react';
import { Page, RunStatus, UserSession, StreamEvent, HistoryRun, API_BASE_URL, stageIcon, statusTone, formatStage, formatDate } from '../types';
export function NewRunPage({
  session,
  onComplete,
  onStatusChange,
  onAuthError,
}: {
  session: UserSession;
  onComplete: () => void;
  onStatusChange: (status: RunStatus) => void;
  onAuthError: () => void;
}) {
  const [targetUrl, setTargetUrl] = useState('');
  const [prompt, setPrompt] = useState('Describe the real user journey to test, the expected result, and any test account or setup notes the agent is allowed to use.');
  
  const [testPlan, setTestPlan] = useState('');
  const [scriptCode, setScriptCode] = useState('');
  const [activeTab, setActiveTab] = useState<'plan' | 'script' | 'logs'>('plan');
  const [isGeneratingPlan, setIsGeneratingPlan] = useState(false);
  const [isGeneratingScript, setIsGeneratingScript] = useState(false);

  const [logs, setLogs] = useState<StreamEvent[]>([]);
  const [status, setStatus] = useState<RunStatus>('READY');
  const [reportUrl, setReportUrl] = useState<string | null>(null);
  const [executionId, setExecutionId] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [logs]);

  const handleGeneratePlan = async () => {
    if (!targetUrl || !prompt) return;
    setIsGeneratingPlan(true);
    setTestPlan('');
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/generate-plan`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${session.token}`
        },
        body: JSON.stringify({ target_url: targetUrl, prompt }),
      });
      if (response.status === 401 || response.status === 403) {
        onAuthError();
        return;
      }
      const data = await response.json();
      if (data.status === 'success') {
        setTestPlan(data.test_plan);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsGeneratingPlan(false);
    }
  };

  const handleGenerateScript = async () => {
    if (!targetUrl || !testPlan) return;
    setIsGeneratingScript(true);
    setScriptCode('');
    setActiveTab('script');
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/generate-script`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${session.token}`
        },
        body: JSON.stringify({ target_url: targetUrl, test_plan: testPlan }),
      });
      if (response.status === 401 || response.status === 403) {
        onAuthError();
        return;
      }
      const data = await response.json();
      if (data.status === 'success') {
        setScriptCode(data.script);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setIsGeneratingScript(false);
    }
  };

  const launchRun = async () => {
    if (!scriptCode) return;
    setActiveTab('logs');
    setStatus('RUNNING');
    onStatusChange('RUNNING');
    setReportUrl(null);
    setExecutionId(null);
    setLogs([{ stage: 'system', message: 'Opening script execution stream.' }]);

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/execute-script/stream`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${session.token}`
        },
        body: JSON.stringify({ target_url: targetUrl, prompt, script_code: scriptCode, test_plan: testPlan }),
      });

      if (response.status === 401 || response.status === 403) {
        onAuthError();
        return;
      }
      if (!response.ok || !response.body) throw new Error('Execution stream failed to start.');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const chunks = buffer.split('\n\n');
        buffer = chunks.pop() || '';
        for (const chunk of chunks) {
          const line = chunk.split('\n').find((item) => item.startsWith('data: '));
          if (!line) continue;
          const event = JSON.parse(line.slice(6)) as StreamEvent;
          setLogs((previous) => [...previous, event]);
          if (event.execution_id) setExecutionId(event.execution_id);
          if (event.report_url) setReportUrl(event.report_url);
          if (event.stage === 'complete') {
            const nextStatus = (event.review_status || 'COMPLETED') as RunStatus;
            setStatus(nextStatus);
            onStatusChange(nextStatus);
            onComplete();
          }
        }
      }
    } catch (error) {
      setStatus('ERROR');
      onStatusChange('ERROR');
      setLogs((previous) => [...previous, { stage: 'error', message: error instanceof Error ? error.message : 'Unknown execution error.' }]);
    }
  };

  return (
    <div className="space-y-6">
      <section className="grid grid-cols-12 gap-6">
        <div className="col-span-12 space-y-6 lg:col-span-12">
          <div className="rounded-md border border-outline-variant/10 bg-surface-container p-6 flex gap-4 items-center">
            <div className="flex-1">
              <label className="mb-3 block font-mono text-[10px] uppercase tracking-widest text-on-surface-variant">Target URL</label>
              <input className="w-full border-b border-outline-variant/30 bg-surface-container-low px-4 py-4 font-mono text-sm text-on-surface outline-none focus:border-primary" placeholder="https://" type="url" value={targetUrl} onChange={(event) => setTargetUrl(event.target.value)} />
            </div>
            <div className="flex-1">
              <label className="mb-3 block font-mono text-[10px] uppercase tracking-widest text-on-surface-variant">Objective</label>
              <input className="w-full border-b border-outline-variant/30 bg-surface-container-low px-4 py-4 font-mono text-sm text-on-surface outline-none focus:border-primary" placeholder="What to test..." type="text" value={prompt} onChange={(event) => setPrompt(event.target.value)} />
            </div>
            <button className="rounded-md bg-gradient-to-r from-primary to-primary-container px-8 py-3 font-bold text-on-primary disabled:opacity-40 self-end mb-1" disabled={!targetUrl || !prompt || isGeneratingPlan} onClick={handleGeneratePlan}>
              {isGeneratingPlan ? 'Generating...' : 'Generate Plan'}
            </button>
          </div>
        </div>
      </section>

      <section className="grid min-h-[500px] grid-cols-12 gap-6">
        <div className="col-span-12 flex flex-col overflow-hidden rounded-md border border-outline-variant/20 bg-surface shadow-2xl lg:col-span-8">
          <div className="flex bg-surface-container-high px-4 py-2 gap-4 border-b border-outline-variant/20">
            <button onClick={() => setActiveTab('plan')} className={`font-mono text-xs uppercase tracking-widest ${activeTab === 'plan' ? 'text-primary font-bold border-b-2 border-primary' : 'text-on-surface-variant'}`}>1. Test Plan</button>
            <button onClick={() => setActiveTab('script')} className={`font-mono text-xs uppercase tracking-widest ${activeTab === 'script' ? 'text-primary font-bold border-b-2 border-primary' : 'text-on-surface-variant'}`}>2. Python Script</button>
            <button onClick={() => setActiveTab('logs')} className={`font-mono text-xs uppercase tracking-widest ${activeTab === 'logs' ? 'text-primary font-bold border-b-2 border-primary' : 'text-on-surface-variant'}`}>3. Execution Logs</button>
          </div>

          {activeTab === 'plan' && (
            <div className="p-6 flex flex-col h-full bg-surface-container-lowest">
              <p className="text-xs text-on-surface-variant mb-2">Review and edit the generated test plan before creating the script.</p>
              <textarea className="flex-1 w-full resize-none border border-outline-variant/20 bg-surface-container-low p-4 text-sm font-mono leading-relaxed text-on-surface outline-none focus:border-primary rounded" value={testPlan} onChange={(e) => setTestPlan(e.target.value)} placeholder="Test plan will appear here..." />
              <button className="mt-4 rounded-md bg-primary px-8 py-3 font-bold text-on-primary disabled:opacity-40 self-start" disabled={!testPlan || isGeneratingScript} onClick={handleGenerateScript}>
                {isGeneratingScript ? 'Generating Script...' : 'Generate Playwright Script'}
              </button>
            </div>
          )}

          {activeTab === 'script' && (
            <div className="p-6 flex flex-col h-full bg-surface-container-lowest">
              <p className="text-xs text-on-surface-variant mb-2">Review the generated Python Playwright script. You can edit the code manually.</p>
              <textarea className="flex-1 w-full resize-none border border-outline-variant/20 bg-black/80 text-green-400 p-4 text-xs font-mono leading-relaxed outline-none focus:border-primary rounded" value={scriptCode} onChange={(e) => setScriptCode(e.target.value)} placeholder="Python Playwright code will appear here..." />
              <button className="mt-4 rounded-md bg-primary px-8 py-3 font-bold text-on-primary disabled:opacity-40 self-start" disabled={!scriptCode || status === 'RUNNING'} onClick={launchRun}>
                Execute Script
              </button>
            </div>
          )}

          {activeTab === 'logs' && (
            <div ref={scrollRef} className="custom-scrollbar flex-1 space-y-6 overflow-y-auto p-6 font-mono text-xs bg-surface-container-lowest">
              {logs.length === 0 ? <p className="text-on-surface-variant">No run initialized.</p> : logs.map((log, index) => (
                <div className="flex gap-x-4" key={`${log.stage}-${index}`}>
                  <div className="flex flex-col items-center">
                    <div className={`flex h-8 w-8 items-center justify-center rounded-full border border-outline-variant/40 bg-surface-container-highest ${log.stage === 'error' ? 'text-error' : 'text-primary'}`}>
                      <span className="material-symbols-outlined text-lg">{stageIcon[log.stage] || 'terminal'}</span>
                    </div>
                    <div className="my-2 h-full w-px bg-outline-variant/20" />
                  </div>
                  <div className="pb-4">
                    <span className="mb-1 block text-[10px] text-on-surface-variant">T + {(index * 0.7 + 0.2).toFixed(1)}s</span>
                    <p className="mb-2 font-medium text-on-surface">{formatStage(log.stage)}</p>
                    <p className="leading-relaxed text-on-surface-variant whitespace-pre-wrap">{log.message}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="col-span-12 rounded-md border border-outline-variant/10 bg-surface-container-low p-6 lg:col-span-4 flex flex-col">
          <p className="font-mono text-[10px] uppercase tracking-widest text-on-surface-variant">Run State</p>
          <div className={`mt-5 inline-flex self-start rounded border px-2 py-1 font-mono text-[10px] ${statusTone(status)}`}>{status}</div>
          <div className="mt-6 grid grid-cols-2 gap-4 border-t border-outline-variant/20 pt-4">
            <div><p className="text-[10px] text-on-surface-variant">EXECUTION ID</p><p className="font-mono text-xs break-all">{executionId || 'pending'}</p></div>
            <div><p className="text-[10px] text-on-surface-variant">REPORT</p><p className="font-mono text-xs">{reportUrl ? 'ready' : 'pending'}</p></div>
          </div>
          {reportUrl && <a className="mt-6 inline-flex rounded border border-primary/40 bg-primary/10 px-4 py-2 text-xs font-bold uppercase tracking-widest text-primary justify-center" href={reportUrl} target="_blank" rel="noreferrer">View Unique Report</a>}
          
          <div className="mt-auto border-t border-outline-variant/20 pt-4">
             <p className="font-mono text-[10px] uppercase tracking-widest text-on-surface-variant mb-2">Decoupled Architecture</p>
             <p className="text-xs text-on-surface-variant">1. Generation is decoupled from Execution.</p>
             <p className="text-xs text-on-surface-variant">2. Standalone Playwright scripts are generated.</p>
             <p className="text-xs text-on-surface-variant">3. Concurrent runs are safely isolated via subprocess.</p>
          </div>
        </div>
      </section>
    </div>
  );
}

