import { FormEvent, useEffect, useState } from 'react';
import {
  AdminStatusRow,
  ParticipantSession,
  adminLogin,
  createAssignment,
  enterParticipantCode,
  fetchAdminStatus,
  fetchHealth,
  importParticipants
} from './api';
import './styles.css';

function App() {
  const [health, setHealth] = useState('Checking backend…');
  const [adminToken, setAdminToken] = useState('');
  const [adminMessage, setAdminMessage] = useState('');
  const [statusRows, setStatusRows] = useState<AdminStatusRow[]>([]);
  const [participantSession, setParticipantSession] = useState<ParticipantSession | null>(null);
  const [participantMessage, setParticipantMessage] = useState('');

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
      </section>
    </main>
  );
}

export default App;
