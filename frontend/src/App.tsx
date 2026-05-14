import { FormEvent, useEffect, useState } from 'react';
import {
  AdminStatusRow,
  DialogueState,
  ParticipantSession,
  QuestionnaireDefinition,
  adminLogin,
  createAssignment,
  enterParticipantCode,
  exportPackage,
  fetchAdminStatus,
  fetchDialogue,
  fetchHealth,
  fetchQuestionnaire,
  finishDialogue,
  importParticipants,
  markSessionExcluded,
  resetPreSurvey,
  sendDialogueMessage,
  submitQuestionnaire
} from './api';
import './styles.css';

const statusLabels: Record<string, string> = {
  not_started: '未开始',
  pre_survey_submitted: '前测已提交',
  chat_in_progress: '对话进行中',
  chat_eligible_to_finish: '对话已达标',
  chat_completed: '对话已完成',
  completed: '实验已完成',
  reset_required: '需要重置',
  excluded: '已排除'
};

const groupLabels: Record<string, string> = {
  experiment: '实验组',
  control: '控制组'
};

const sourceLabels: Record<string, string> = {
  imported: '导入指定',
  randomized: '系统随机'
};

function labelFor(labels: Record<string, string>, value: string | null | undefined): string {
  if (!value) return '—';
  return labels[value] ?? value;
}

function App() {
  const [health, setHealth] = useState('正在检查后端…');
  const [adminToken, setAdminToken] = useState('');
  const [adminMessage, setAdminMessage] = useState('');
  const [adminActionReason, setAdminActionReason] = useState('');
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
        setHealth(`后端 ${data.app}；数据库${data.database.ok ? '正常' : '不可用'}`);
      })
      .catch((error: Error) => setHealth(`后端不可用：${error.message}`));
  }, []);

  async function handleAdminLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const username = String(data.get('username') ?? '');
    const password = String(data.get('password') ?? '');
    const login = await adminLogin(username, password);
    setAdminToken(login.token);
    setAdminMessage('研究者已登录。');
  }

  async function handleImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const participantCode = String(data.get('participant_code') ?? '');
    const assignedGroup = String(data.get('assigned_group') ?? '');
    const result = await importParticipants(adminToken, [
      { participant_code: participantCode, assigned_group: assignedGroup }
    ]);
    setAdminMessage(`已导入 ${result.imported_count} 个被试编号。`);
    await refreshStatus(adminToken);
  }

  async function refreshStatus(token = adminToken) {
    if (!token) return;
    const status = await fetchAdminStatus(token);
    setStatusRows(status.participants);
  }

  async function handleResetPreSurvey(sessionId: string) {
    if (!adminToken || !adminActionReason.trim()) {
      setAdminMessage('重置前请填写审计原因。');
      return;
    }
    await resetPreSurvey(adminToken, sessionId, adminActionReason);
    setAdminMessage('前测已重置，审计原因已记录。');
    await refreshStatus();
  }

  async function handleExcludeSession(sessionId: string) {
    if (!adminToken || !adminActionReason.trim()) {
      setAdminMessage('排除前请填写排除原因。');
      return;
    }
    await markSessionExcluded(adminToken, sessionId, adminActionReason);
    setAdminMessage('实验会话已标记为排除，并已记录审计日志。');
    await refreshStatus();
  }

  async function handleExportPackage() {
    if (!adminToken) return;
    const blob = await exportPackage(adminToken);
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `mentor-echo-export-${new Date().toISOString().replace(/[:.]/g, '-')}.zip`;
    link.click();
    URL.revokeObjectURL(url);
    setAdminMessage('导出 ZIP 已生成。原始聊天为敏感数据，已与 analysis_dataset.csv 分离。');
    await refreshStatus();
  }

  async function handleParticipantEntry(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const participantCode = String(data.get('participant_code') ?? '');
    const result = await enterParticipantCode(participantCode);
    setParticipantSession(result.session);
    setParticipantMessage(
      `实验会话状态：${labelFor(statusLabels, result.session.status)}；分组已锁定：${result.session.assignment_locked ? '是' : '否'}`
    );
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
    setParticipantMessage(
      `分组已锁定：${labelFor(groupLabels, assignment.group)}（${labelFor(sourceLabels, assignment.assignment_source)}）`
    );
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
    setParticipantMessage(
      `${questionnaire.phase === 'pre' ? '前测' : '后测'}已提交并锁定（${result.response_count} 条回答）。`
    );
    setQuestionnaire({ ...questionnaire, locked: true });
    await refreshStatus();
  }

  async function handleStartDialogue() {
    if (!participantSession) return;
    const state = await fetchDialogue(participantSession.experiment_session_id);
    setDialogue(state);
    setParticipantMessage(
      `AI 对话已开始：${labelFor(groupLabels, state.group)}；提示词版本 ${state.system_prompt_version}。`
    );
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
    setParticipantMessage(`对话状态：${labelFor(statusLabels, result.status)}`);
    await refreshStatus();
  }

  return (
    <main>
      <header>
        <p className="eyebrow">Mentor Echo MVP</p>
        <h1>AI 对话实验平台</h1>
        <p data-testid="health-status" className="health">{health}</p>
      </header>

      <section aria-labelledby="admin-heading" className="panel">
        <h2 id="admin-heading">研究者管理端</h2>
        <form onSubmit={handleAdminLogin} className="row-form">
          <input name="username" placeholder="研究者账号" defaultValue="researcher" aria-label="研究者账号" />
          <input name="password" placeholder="研究者密码" type="password" aria-label="研究者密码" />
          <button type="submit">登录</button>
        </form>
        <form onSubmit={handleImport} className="row-form">
          <input name="participant_code" placeholder="被试编号" aria-label="导入被试编号" />
          <select name="assigned_group" aria-label="分组" defaultValue="">
            <option value="">稍后随机分组</option>
            <option value="experiment">实验组</option>
            <option value="control">控制组</option>
          </select>
          <button type="submit" disabled={!adminToken}>导入被试</button>
          <button type="button" disabled={!adminToken} onClick={() => refreshStatus()}>刷新状态</button>
          <button type="button" disabled={!adminToken} onClick={handleExportPackage}>导出 ZIP</button>
        </form>
        <label className="stacked-field">
          审计 / 排除原因
          <input
            value={adminActionReason}
            onChange={(event) => setAdminActionReason(event.target.value)}
            placeholder="重置或排除前必须填写原因"
            aria-label="管理员操作原因"
          />
        </label>
        <p>{adminMessage}</p>
        <table>
          <thead>
            <tr>
              <th>被试编号</th>
              <th>状态</th>
              <th>分组</th>
              <th>来源</th>
              <th>问卷</th>
              <th>轮次</th>
              <th>时长</th>
              <th>完成资格</th>
              <th>完成情况</th>
              <th>排除状态</th>
              <th>恢复次数</th>
              <th>最后访问</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {statusRows.map((row) => (
              <tr key={row.participant_code}>
                <td>{row.participant_code}</td>
                <td>{labelFor(statusLabels, row.status)}</td>
                <td>{labelFor(groupLabels, row.group)}</td>
                <td>{labelFor(sourceLabels, row.assignment_source)}</td>
                <td>
                  前测 {row.pre_survey_submitted ? '✓' : '—'} / 后测 {row.post_survey_submitted ? '✓' : '—'}
                </td>
                <td>{row.participant_turn_count}</td>
                <td>{row.dialogue_elapsed_minutes} 分钟</td>
                <td>{row.dialogue_completion_eligible ? '已达标' : '未达标'}</td>
                <td>{row.completed ? '实验完成' : row.dialogue_completed ? '对话完成' : '未完成'}</td>
                <td>{row.excluded ? `已排除：${row.exclusion_reason ?? ''}` : '纳入'}</td>
                <td>{row.resume_count}</td>
                <td>{row.last_seen_at ? new Date(row.last_seen_at).toLocaleString() : '—'}</td>
                <td>
                  <button
                    type="button"
                    disabled={!row.experiment_session_id}
                    onClick={() => row.experiment_session_id && handleResetPreSurvey(row.experiment_session_id)}
                  >
                    重置前测
                  </button>
                  <button
                    type="button"
                    disabled={!row.experiment_session_id || row.excluded}
                    onClick={() => row.experiment_session_id && handleExcludeSession(row.experiment_session_id)}
                  >
                    排除
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section aria-labelledby="participant-heading" className="panel">
        <h2 id="participant-heading">被试入口</h2>
        <form onSubmit={handleParticipantEntry} className="row-form">
          <input name="participant_code" placeholder="被试编号" aria-label="被试编号" />
          <button type="submit">进入实验</button>
        </form>
        <button type="button" disabled={!participantSession} onClick={handleAssignment}>
          创建 / 确认锁定分组
        </button>
        <p>{participantMessage}</p>
        {participantSession ? (
          <dl>
            <dt>被试编号</dt>
            <dd>{participantSession.participant_code}</dd>
            <dt>实验会话</dt>
            <dd>{participantSession.experiment_session_id}</dd>
            <dt>分组</dt>
            <dd>{labelFor(groupLabels, participantSession.group)}</dd>
            <dt>分组来源</dt>
            <dd>{labelFor(sourceLabels, participantSession.assignment_source)}</dd>
          </dl>
        ) : null}
        <div className="stage-actions">
          <button type="button" disabled={!participantSession} onClick={() => loadQuestionnaire('pre')}>
            加载前测问卷
          </button>
          <button type="button" disabled={!participantSession} onClick={handleStartDialogue}>
            开始 / 继续 AI 对话
          </button>
          <button type="button" disabled={!participantSession} onClick={() => loadQuestionnaire('post')}>
            加载后测问卷
          </button>
        </div>
      </section>

      {questionnaire ? (
        <section aria-labelledby="questionnaire-heading" className="panel">
          <h2 id="questionnaire-heading">
            {questionnaire.phase === 'pre' ? '前测问卷' : '后测问卷'}
          </h2>
          <p>版本：{questionnaire.questionnaire_version}</p>
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
              提交并锁定{questionnaire.phase === 'pre' ? '前测' : '后测'}
            </button>
          </form>
        </section>
      ) : null}

      {dialogue ? (
        <section aria-labelledby="dialogue-heading" className="panel">
          <h2 id="dialogue-heading">AI 对话</h2>
          <p>
            进度：{dialogue.progress.participant_turn_count}/{dialogue.progress.required_participant_turns}
            {' '}条被试消息；{dialogue.progress.dialogue_elapsed_seconds}/{dialogue.progress.required_elapsed_seconds}
            {' '}秒。
          </p>
          <p data-testid="finish-eligibility">
            完成资格：{dialogue.progress.eligible_to_finish ? '已达标' : '未达标'}
          </p>
          <div className="messages">
            {dialogue.messages.map((message) => (
              <p key={message.id}><strong>{message.role === 'participant' ? '被试' : 'AI'}：</strong> {message.content}</p>
            ))}
          </div>
          <form onSubmit={handleSendDialogueMessage} className="row-form">
            <input
              aria-label="对话内容"
              value={dialogueInput}
              onChange={(event) => setDialogueInput(event.target.value)}
              placeholder="输入你的对话内容"
            />
            <button type="submit">发送</button>
          </form>
          <button
            type="button"
            disabled={!dialogue.progress.eligible_to_finish}
            onClick={handleFinishDialogue}
          >
            结束对话 / 进入后测
          </button>
        </section>
      ) : null}
    </main>
  );
}

export default App;
