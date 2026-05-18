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
  pre_survey_submitted: boolean;
  post_survey_submitted: boolean;
  participant_turn_count: number;
  dialogue_elapsed_seconds: number;
  dialogue_elapsed_minutes: number;
  met_min_turns: boolean;
  met_min_duration: boolean;
  dialogue_completion_eligible: boolean;
  dialogue_completed: boolean;
  completed: boolean;
  excluded: boolean;
  exclusion_reason: string | null;
  topic_off_track_ratio: number | null;
  topic_off_track_gt_30pct: boolean | null;
  topic_validity_status: string;
  topic_validity_notes: string | null;
  topic_validity_coded_at: string | null;
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
  last_seen_at: string | null;
  started_at: string;
  completed_at: string | null;
};

export type QuestionnaireItem = {
  phase: 'pre' | 'post';
  order: number;
  item_key: string;
  item_text: string;
  item_type: string;
  scale: string;
  instrument: string;
  dimension: string;
  reverse_scored: boolean;
  required: boolean;
  attention_check: boolean;
};

export type ScaleProfile = {
  key: string;
  value_type: 'integer' | 'categorical';
  min_value: number | null;
  max_value: number | null;
  labels: Record<string, string> | null;
  options: string[];
};

export type QuestionnaireDefinition = {
  questionnaire_version: string;
  phase: 'pre' | 'post';
  locked: boolean;
  items: QuestionnaireItem[];
  scales: Record<string, ScaleProfile>;
};

export type DialogueState = {
  experiment_session_id: string;
  participant_code: string;
  group: 'experiment' | 'control';
  system_prompt_version: string;
  status: string;
  progress: {
    participant_turn_count: number;
    dialogue_elapsed_seconds: number;
    met_min_turns: boolean;
    met_min_duration: boolean;
    eligible_to_finish: boolean;
    required_participant_turns: number;
    required_elapsed_seconds: number;
    max_participant_turns: number;
    max_elapsed_seconds: number;
    finish_prompt_visible: boolean;
    forced_to_finish: boolean;
    forced_finish_reason: string | null;
    finish_decision: string | null;
    continue_until_turn_count: number | null;
    reminder_due: boolean;
    reminder_text: string;
  };
  messages: Array<{
    id: string;
    message_index: number;
    role: string;
    content: string;
    provider_name: string | null;
    model_name: string | null;
    system_prompt_version: string | null;
    generation_params: Record<string, object> | null;
    duration_ms: number | null;
    retry_count: number | null;
    error_code: string | null;
    error_message_sanitized: string | null;
    created_at: string;
  }>;
};

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) },
    ...options
  });
  if (!response.ok) {
    const detail = await response.text();
    let message = detail || `Request failed with ${response.status}`;
    try {
      const parsed = JSON.parse(detail) as { detail?: unknown };
      if (typeof parsed.detail === 'string') {
        message = parsed.detail;
      }
    } catch {
      // Keep the raw response body when the API did not return JSON.
    }
    throw new Error(message);
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

export function resetPreSurvey(token: string, sessionId: string, reason: string): Promise<{ reset: boolean }> {
  return request(`/api/admin/sessions/${sessionId}/questionnaires/pre/reset`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({ reason })
  });
}

export function markSessionExcluded(
  token: string,
  sessionId: string,
  reason: string
): Promise<{ experiment_session_id: string; status: string; excluded: boolean; exclusion_reason: string | null }> {
  return request(`/api/admin/sessions/${sessionId}/exclusion`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({ excluded: true, reason })
  });
}

export async function exportPackage(token: string): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}/api/admin/export`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` }
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with ${response.status}`);
  }
  return response.blob();
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

export function fetchQuestionnaire(sessionId: string, phase: 'pre' | 'post'): Promise<QuestionnaireDefinition> {
  return request(`/api/participant/sessions/${sessionId}/questionnaires/${phase}`);
}

export function submitQuestionnaire(
  sessionId: string,
  phase: 'pre' | 'post',
  responses: Record<string, string | number>
): Promise<{ session: ParticipantSession; response_count: number; locked: boolean }> {
  return request(`/api/participant/sessions/${sessionId}/questionnaires/${phase}/submit`, {
    method: 'POST',
    body: JSON.stringify({ responses })
  });
}

export function fetchDialogue(sessionId: string): Promise<DialogueState> {
  return request(`/api/participant/sessions/${sessionId}/dialogue`);
}

export function sendDialogueMessage(
  sessionId: string,
  content: string
): Promise<{ progress: DialogueState['progress']; status: string }> {
  return request(`/api/participant/sessions/${sessionId}/dialogue/messages`, {
    method: 'POST',
    body: JSON.stringify({ content })
  });
}

export type DialogueFinishDecision = 'can_end' | 'continue_related' | 'not_core' | 'early_stop';

export function finishDialogue(
  sessionId: string,
  decision: DialogueFinishDecision
): Promise<{ status: string; progress: DialogueState['progress'] }> {
  return request(`/api/participant/sessions/${sessionId}/dialogue/finish`, {
    method: 'POST',
    body: JSON.stringify({ decision })
  });
}
