const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export type HealthResponse = {
  app: string;
  database: { ok: boolean };
};

export type AdminStatusRow = {
  participant_code: string;
  assigned_group_imported: 'experiment' | 'control' | null;
  experiment_session_id: string | null;
  status: string;
  group: 'experiment' | 'control' | null;
  assignment_source: 'imported' | 'randomized' | null;
  assignment_locked: boolean;
  resume_count: number;
  last_seen_at: string | null;
};

export type ParticipantSession = {
  experiment_session_id: string;
  participant_code: string;
  status: string;
  group: 'experiment' | 'control' | null;
  assignment_source: 'imported' | 'randomized' | null;
  assignment_locked: boolean;
  resume_count: number;
};

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) },
    ...options
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with ${response.status}`);
  }
  return (await response.json()) as T;
}

export function fetchHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/api/health');
}

export function adminLogin(username: string, password: string): Promise<{ token: string }> {
  return request('/api/admin/login', {
    method: 'POST',
    body: JSON.stringify({ username, password })
  });
}

export function importParticipants(
  token: string,
  participants: Array<{ participant_code: string; assigned_group?: string }>
): Promise<{ imported_count: number; participant_codes: string[] }> {
  return request('/api/admin/participants/import', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({ participants })
  });
}

export function fetchAdminStatus(token: string): Promise<{ participants: AdminStatusRow[] }> {
  return request('/api/admin/status', {
    headers: { Authorization: `Bearer ${token}` }
  });
}

export function enterParticipantCode(participantCode: string): Promise<{ session: ParticipantSession }> {
  return request('/api/participant/entry', {
    method: 'POST',
    body: JSON.stringify({ participant_code: participantCode })
  });
}

export function createAssignment(sessionId: string): Promise<{
  experiment_session_id: string;
  participant_code: string;
  group: 'experiment' | 'control';
  assignment_source: 'imported' | 'randomized';
  assignment_locked: boolean;
}> {
  return request(`/api/participant/sessions/${sessionId}/assignment`, { method: 'POST' });
}
