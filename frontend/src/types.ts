import React, { useEffect, useMemo, useRef, useState } from 'react';

export type Page = 'login' | 'dashboard' | 'new-run' | 'history' | 'run-detail';
export type RunStatus = 'READY' | 'RUNNING' | 'PASS' | 'FAIL' | 'BLOCKED' | 'ERROR' | 'COMPLETED';

export type UserSession = {
  userId: string;
  email: string;
  token?: string;
};

export type StreamEvent = {
  stage: string;
  message: string;
  execution_id?: string;
  review_status?: string;
  report_url?: string | null;
};

export type HistoryRun = {
  _id: string;
  user_id: string;
  execution_id?: string;
  target_url?: string;
  prompt: string;
  status: string;
  pdf_path: string;
  report_url?: string | null;
  result?: string | null;
  test_plan?: string;
  script_code?: string;
  created_at?: string;
};

export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const stageIcon: Record<string, string> = {
  system: 'memory',
  planner: 'psychology',
  executor: 'precision_manufacturing',
  tool_call: 'mouse',
  tool_result: 'visibility',
  agent_response: 'forum',
  reviewer: 'fact_check',
  recovery: 'restart_alt',
  database: 'database',
  complete: 'task_alt',
  error: 'warning',
};

export const statusTone = (status: string) => {
  if (status === 'PASS') return 'text-success bg-success/10 border-success/30';
  if (status === 'FAIL' || status === 'FAILED' || status === 'ERROR') return 'text-error bg-error/10 border-error/30';
  if (status === 'BLOCKED') return 'text-warning bg-warning/10 border-warning/30';
  return 'text-primary bg-primary/10 border-primary/20';
};

export const formatStage = (stage: string) => stage.replace(/_/g, ' ').toUpperCase();
export const formatDate = (value?: string) => (value ? new Date(value).toLocaleString() : 'Unknown time');

