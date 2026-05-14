import { FormEvent, useEffect, useState } from 'react';
import {
  AdminStatusRow,
  DialogueState,
  ParticipantSession,
  QuestionnaireDefinition,
  adminLogin,
  createAssignment,
  enterParticipantCode,
  fetchAdminStatus,
  fetchDialogue,
  fetchHealth,
  fetchQuestionnaire,
  finishDialogue,
  importParticipants,
  sendDialogueMessage,
  submitQuestionnaire
} from './api';
import './styles.css';

function App() {
  const [health, setHealth] = useState('Checking backend…');
  const [adminToken, setAdminToken] = useState('');
  const [adminMessage, setAdminMessage] = useState('');
  const [statusRows, setStatusRows] = useState<AdminStatusRow[]>([]);
  const [participantSession, setParticipantSession] = useState<ParticipantSession | null>(null);
  const [participantMessage, setParticipantMessage] = useState('');
  const [questionnaire, setQuestionnaire] = useState<QuestionnaireDefinition | null>(null);
  const [questionnaireResponses, setQuestionnaireResponses] = useState<Record<string, string | number>>({});
  const [dialogue, setDialogue] = useState<DialogueState | null>(null);
  const [dialogueInput, setDialogueInput] = useState('');

  useEffect(() => {
    fetchHealth()
      .then((data) => {
        setHealth(`Backend ${data.app}; database ${data.database.ok ? 'ok' : 'unavailable'}`);
      })
      .catch((error: Error) => setHealth(`Backend unavailable: ${error.message}`));
  }, []);

  async function handleAdminLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const username = String(data.get('username') ?? '');
    const password = String(data.get('password') ?? '');
    const login = await adminLogin(username, password);
    setAdminToken(login.token);
    setAdminMessage('Admin signed in.');
  }

  async function handleImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const participantCode = String(data.get('participant_code') ?? '');
    const assignedGroup = String(data.get('assigned_group') ?? '');
    const result = await importParticipants(adminToken, [
      { participant_code: participantCode, assigned_group: assignedGroup }
    ]);
    setAdminMessage(`Imported ${result.imported_count} participant code(s).`);
    await refreshStatus(adminToken);
  }

  async function refreshStatus(token = adminToken) {
    if (!token) return;
    const status = await fetchAdminStatus(token);
    setStatusRows(status.participants);
  }

  async function handleParticipantEntry(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const participantCode = String(data.get('participant_code') ?? '');
    const result = await enterParticipantCode(participantCode);
    setParticipantSession(result.session);
    setParticipantMessage(`Session ${result.session.status}; assignment locked: ${result.session.assignment_locked}`);
    setQuestionnaire(null);
    setDialogue(null);
  }

  async function handleAssignment() {
    if (!participantSession) return;
    const assignment = await createAssignment(participantSession.experiment_session_id);
    setParticipantSession({
      ...participantSession,
      group: assignment.group,
      assignment_source: assignment.assignment_source,
      assignment_locked: assignment.assignment_locked
    });
    setParticipantMessage(`Assignment locked: ${assignment.group} (${assignment.assignment_source})`);
    await refreshStatus();
  }

  async function loadQuestionnaire(phase: 'pre' | 'post') {
    if (!participantSession) return;
    const definition = await fetchQuestionnaire(participantSession.experiment_session_id, phase);
    const defaults: Record<string, string | number> = {};
    for (const item of definition.items) {
      const scale = definition.scales[item.scale];
      defaults[item.item_key] =
        scale.value_type === 'categorical' ? scale.options[0] : (scale.min_value ?? 1);
    }
    setQuestionnaire(definition);
    setQuestionnaireResponses(defaults);
  }

  async function handleQuestionnaireSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!participantSession || !questionnaire) return;
    const result = await submitQuestionnaire(
      participantSession.experiment_session_id,
      questionnaire.phase,
      questionnaireResponses
    );
    setParticipantSession(result.session);
    setParticipantMessage(`${questionnaire.phase}-survey submitted and locked (${result.response_count} responses).`);
    setQuestionnaire({ ...questionnaire, locked: true });
    await refreshStatus();
  }

  async function handleStartDialogue() {
    if (!participantSession) return;
    const state = await fetchDialogue(participantSession.experiment_session_id);
    setDialogue(state);
    setParticipantMessage(`Dialogue started for ${state.group}; prompt ${state.system_prompt_version}.`);
  }

  async function handleSendDialogueMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!participantSession || !dialogueInput.trim()) return;
    await sendDialogueMessage(participantSession.experiment_session_id, dialogueInput);
    const state = await fetchDialogue(participantSession.experiment_session_id);
    setDialogue(state);
    setDialogueInput('');
    setParticipantSession({ ...participantSession, status: state.status });
  }

  async function handleFinishDialogue() {
    if (!participantSession) return;
    const result = await finishDialogue(participantSession.experiment_session_id);
    setParticipantSession({ ...participantSession, status: result.status });
    const state = await fetchDialogue(participantSession.experiment_session_id).catch(() => null);
    if (state) setDialogue(state);
    setParticipantMessage(`Dialogue status: ${result.status}`);
    await refreshStatus();
  }

  return (
    <main>
      <header>
        <p className="eyebrow">Mentor Echo MVP</p>
        <h1>Experiment foundation tracer</h1>
        <p data-testid="health-status" className="health">{health}</p>
      </header>

      <section aria-labelledby="admin-heading" className="panel">
        <h2 id="admin-heading">Researcher administrator</h2>
        <form onSubmit={handleAdminLogin} className="row-form">
          <input name="username" placeholder="username" defaultValue="researcher" aria-label="admin username" />
          <input name="password" placeholder="password" type="password" aria-label="admin password" />
          <button type="submit">Sign in</button>
        </form>
        <form onSubmit={handleImport} className="row-form">
          <input name="participant_code" placeholder="participant code" aria-label="import participant code" />
          <select name="assigned_group" aria-label="assigned group" defaultValue="">
            <option value="">Randomize later</option>
            <option value="experiment">Experiment</option>
            <option value="control">Control</option>
          </select>
          <button type="submit" disabled={!adminToken}>Import</button>
          <button type="button" disabled={!adminToken} onClick={() => refreshStatus()}>Refresh status</button>
        </form>
        <p>{adminMessage}</p>
        <table>
          <thead>
            <tr>
              <th>Participant Code</th>
              <th>Status</th>
              <th>Group</th>
              <th>Source</th>
              <th>Resume Count</th>
            </tr>
          </thead>
          <tbody>
            {statusRows.map((row) => (
              <tr key={row.participant_code}>
                <td>{row.participant_code}</td>
                <td>{row.status}</td>
                <td>{row.group ?? '—'}</td>
                <td>{row.assignment_source ?? '—'}</td>
                <td>{row.resume_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section aria-labelledby="participant-heading" className="panel">
        <h2 id="participant-heading">Participant entry</h2>
        <form onSubmit={handleParticipantEntry} className="row-form">
          <input name="participant_code" placeholder="participant code" aria-label="participant code" />
          <button type="submit">Enter</button>
        </form>
        <button type="button" disabled={!participantSession} onClick={handleAssignment}>
          Create/confirm locked assignment
        </button>
        <p>{participantMessage}</p>
        {participantSession ? (
          <dl>
            <dt>Participant Code</dt>
            <dd>{participantSession.participant_code}</dd>
            <dt>Experiment Session</dt>
            <dd>{participantSession.experiment_session_id}</dd>
            <dt>Group</dt>
            <dd>{participantSession.group ?? 'not assigned yet'}</dd>
            <dt>Assignment Source</dt>
            <dd>{participantSession.assignment_source ?? 'not assigned yet'}</dd>
          </dl>
        ) : null}
        <div className="stage-actions">
          <button type="button" disabled={!participantSession} onClick={() => loadQuestionnaire('pre')}>
            Load pre-survey
          </button>
          <button type="button" disabled={!participantSession} onClick={handleStartDialogue}>
            Start / resume AI Dialogue
          </button>
          <button type="button" disabled={!participantSession} onClick={() => loadQuestionnaire('post')}>
            Load post-survey
          </button>
        </div>
      </section>

      {questionnaire ? (
        <section aria-labelledby="questionnaire-heading" className="panel">
          <h2 id="questionnaire-heading">
            {questionnaire.phase === 'pre' ? 'Pre-survey' : 'Post-survey'}
          </h2>
          <p>Version: {questionnaire.questionnaire_version}</p>
          <form onSubmit={handleQuestionnaireSubmit}>
            <div className="questionnaire-list">
              {questionnaire.items.map((item) => {
                const scale = questionnaire.scales[item.scale];
                return (
                  <label key={item.item_key}>
                    <span>{item.order}. {item.item_text}</span>
                    {scale.value_type === 'categorical' ? (
                      <select
                        value={String(questionnaireResponses[item.item_key] ?? '')}
                        disabled={questionnaire.locked}
                        onChange={(event) =>
                          setQuestionnaireResponses({
                            ...questionnaireResponses,
                            [item.item_key]: event.target.value
                          })
                        }
                      >
                        {scale.options.map((option) => (
                          <option key={option} value={option}>{option}</option>
                        ))}
                      </select>
                    ) : (
                      <select
                        value={String(questionnaireResponses[item.item_key] ?? scale.min_value ?? 1)}
                        disabled={questionnaire.locked}
                        onChange={(event) =>
                          setQuestionnaireResponses({
                            ...questionnaireResponses,
                            [item.item_key]: Number(event.target.value)
                          })
                        }
                      >
                        {Array.from(
                          { length: (scale.max_value ?? 1) - (scale.min_value ?? 1) + 1 },
                          (_, index) => (scale.min_value ?? 1) + index
                        ).map((value) => (
                          <option key={value} value={value}>
                            {value} {scale.labels?.[String(value)] ?? ''}
                          </option>
                        ))}
                      </select>
                    )}
                  </label>
                );
              })}
            </div>
            <button type="submit" disabled={questionnaire.locked}>
              Submit and lock {questionnaire.phase}-survey
            </button>
          </form>
        </section>
      ) : null}

      {dialogue ? (
        <section aria-labelledby="dialogue-heading" className="panel">
          <h2 id="dialogue-heading">AI Dialogue</h2>
          <p>
            Progress: {dialogue.progress.participant_turn_count}/{dialogue.progress.required_participant_turns}
            {' '}participant turns; {dialogue.progress.dialogue_elapsed_seconds}/{dialogue.progress.required_elapsed_seconds}
            {' '}seconds.
          </p>
          <p data-testid="finish-eligibility">
            Finish eligibility: {dialogue.progress.eligible_to_finish ? 'eligible' : 'not eligible'}
          </p>
          <div className="messages">
            {dialogue.messages.map((message) => (
              <p key={message.id}><strong>{message.role}:</strong> {message.content}</p>
            ))}
          </div>
          <form onSubmit={handleSendDialogueMessage} className="row-form">
            <input
              aria-label="dialogue message"
              value={dialogueInput}
              onChange={(event) => setDialogueInput(event.target.value)}
              placeholder="Type your dialogue message"
            />
            <button type="submit">Send</button>
          </form>
          <button
            type="button"
            disabled={!dialogue.progress.eligible_to_finish}
            onClick={handleFinishDialogue}
          >
            Finish dialogue / enter post-survey
          </button>
        </section>
      ) : null}
    </main>
  );
}

export default App;
