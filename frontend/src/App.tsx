import { FormEvent, ReactNode, useEffect, useMemo, useState } from 'react';
import {
  AdminStatusRow,
  DialogueState,
  ParticipantSession,
  QuestionnaireDefinition,
  QuestionnaireItem,
  ScaleProfile,
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

type Route = 'landing' | 'participant' | 'admin';
type Phase = 'pre' | 'post';
type ParticipantStep =
  | 'entry'
  | 'welcome'
  | 'pre'
  | 'ai-guide'
  | 'dialogue'
  | 'post-guide'
  | 'post'
  | 'complete'
  | 'blocked';

const statusLabels: Record<string, string> = {
  not_started: '未开始',
  pre_survey_submitted: '前测完成',
  chat_in_progress: '对话中',
  chat_eligible_to_finish: '对话已达标',
  chat_completed: '对话完成',
  completed: '已完成',
  reset_required: '需要研究者处理',
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
  if (!value) return '暂无';
  return labels[value] ?? value;
}

function formatDuration(totalSeconds: number | null | undefined): string {
  const safeSeconds = Math.max(0, Math.floor(totalSeconds ?? 0));
  const minutes = Math.floor(safeSeconds / 60);
  const seconds = safeSeconds % 60;
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

function toParticipantStep(session: ParticipantSession): ParticipantStep {
  if (session.status === 'excluded' || session.status === 'reset_required') return 'blocked';
  if (session.status === 'completed') return 'complete';
  if (session.status === 'chat_completed') return 'post-guide';
  if (session.status === 'chat_in_progress' || session.status === 'chat_eligible_to_finish') return 'dialogue';
  if (session.status === 'pre_survey_submitted') return 'ai-guide';
  return 'welcome';
}

function userFacingError(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error);
  if (message.includes('Invalid credentials')) return '研究者账号或密码不正确。';
  if (message.includes('Admin token required')) return '研究者登录已失效，请重新登录。';
  if (message.includes('Post-survey is available only after dialogue completion')) {
    return '后测问卷会在 AI 对话完成后开放。';
  }
  if (message.includes('Pre-survey is not available')) return '当前阶段不能填写前测问卷。';
  if (message.includes('Group Assignment is required before dialogue')) {
    return '系统正在准备 AI 对话，请稍后重试。';
  }
  if (message.includes('Experiment Session not found')) return '未找到实验进度，请重新输入被试编号。';
  return message || '操作失败，请稍后重试。';
}

function App() {
  const [route, setRoute] = useState<Route>('landing');
  const [health, setHealth] = useState('正在连接后端');

  useEffect(() => {
    fetchHealth()
      .then((data) => {
        setHealth(`后端 ${data.app}，数据库${data.database.ok ? '正常' : '不可用'}`);
      })
      .catch((error: Error) => setHealth(`后端不可用：${error.message}`));
  }, []);

  return (
    <main className="app-shell">
      <header className="topbar">
        <button className="brand-button" type="button" onClick={() => setRoute('landing')}>
          Mentor Echo
        </button>
        <p data-testid="health-status" className="health">
          {health}
        </p>
      </header>

      {route === 'landing' ? <LandingPage onSelect={setRoute} /> : null}
      {route === 'participant' ? <ParticipantFlow onBack={() => setRoute('landing')} /> : null}
      {route === 'admin' ? <AdminFlow onBack={() => setRoute('landing')} /> : null}
    </main>
  );
}

function LandingPage({ onSelect }: { onSelect: (route: Route) => void }) {
  return (
    <section className="landing" aria-labelledby="landing-title">
      <div className="landing-copy">
        <p className="eyebrow">AI 对话实验</p>
        <h1 id="landing-title">Mentor Echo AI 对话实验平台</h1>
        <p>
          使用研究者提供的被试编号进入实验。平台只保存编号和实验数据，不收集你的姓名。
        </p>
      </div>
      <div className="role-actions" aria-label="选择入口">
        <button type="button" className="primary-action" onClick={() => onSelect('participant')}>
          我是被试，进入实验
        </button>
        <button type="button" className="secondary-action" onClick={() => onSelect('admin')}>
          我是研究者，进入管理后台
        </button>
      </div>
    </section>
  );
}

function ParticipantFlow({ onBack }: { onBack: () => void }) {
  const [step, setStep] = useState<ParticipantStep>('entry');
  const [session, setSession] = useState<ParticipantSession | null>(null);
  const [questionnaire, setQuestionnaire] = useState<QuestionnaireDefinition | null>(null);
  const [responses, setResponses] = useState<Record<Phase, Record<string, string | number>>>({
    pre: {},
    post: {}
  });
  const [dirtyPhase, setDirtyPhase] = useState<Phase | null>(null);
  const [dialogue, setDialogue] = useState<DialogueState | null>(null);
  const [dialogueInput, setDialogueInput] = useState('');
  const [statusMessage, setStatusMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const hasUnsavedAnswers = dirtyPhase !== null && questionnaire?.locked !== true;

  useEffect(() => {
    if (!hasUnsavedAnswers) return;
    const warnBeforeLeaving = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', warnBeforeLeaving);
    return () => window.removeEventListener('beforeunload', warnBeforeLeaving);
  }, [hasUnsavedAnswers]);

  async function handleEntry(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError('');
    setStatusMessage('');
    const data = new FormData(event.currentTarget);
    const participantCode = String(data.get('participant_code') ?? '').trim();
    try {
      const result = await enterParticipantCode(participantCode);
      const nextStep = toParticipantStep(result.session);
      setSession(result.session);
      setStep(nextStep);
      setQuestionnaire(null);
      if (nextStep === 'dialogue') {
        const state = await fetchDialogue(result.session.experiment_session_id);
        setDialogue(state);
        setSession({ ...result.session, status: state.status });
      } else {
        setDialogue(null);
      }
      setStatusMessage('已恢复你的实验进度，请按照页面提示继续。');
    } catch (entryError) {
      setError(userFacingError(entryError));
    } finally {
      setBusy(false);
    }
  }

  async function ensureAssignment(currentSession: ParticipantSession): Promise<ParticipantSession> {
    if (currentSession.assignment_locked) return currentSession;
    const assignment = await createAssignment(currentSession.experiment_session_id);
    const updated = {
      ...currentSession,
      group: assignment.group,
      assignment_source: assignment.assignment_source,
      assignment_locked: assignment.assignment_locked
    };
    setSession(updated);
    return updated;
  }

  async function loadQuestionnaire(phase: Phase) {
    if (!session) return;
    setBusy(true);
    setError('');
    setStatusMessage('');
    try {
      const definition = await fetchQuestionnaire(session.experiment_session_id, phase);
      setQuestionnaire(definition);
      setStep(phase);
    } catch (loadError) {
      setError(userFacingError(loadError));
    } finally {
      setBusy(false);
    }
  }

  async function handleQuestionnaireSubmit(phase: Phase, phaseResponses: Record<string, string | number>) {
    if (!session || !questionnaire) return;
    setBusy(true);
    setError('');
    try {
      const result = await submitQuestionnaire(session.experiment_session_id, phase, phaseResponses);
      setSession(result.session);
      setQuestionnaire({ ...questionnaire, locked: true });
      setDirtyPhase(null);
      if (phase === 'pre') {
        await ensureAssignment(result.session);
        setStatusMessage('前测已提交并锁定。');
        setStep('ai-guide');
      } else {
        setStatusMessage('后测已提交并锁定。');
        setStep('complete');
      }
    } catch (submitError) {
      setError(userFacingError(submitError));
    } finally {
      setBusy(false);
    }
  }

  async function handleStartDialogue() {
    if (!session) return;
    setBusy(true);
    setError('');
    setStatusMessage('');
    try {
      const assignedSession = await ensureAssignment(session);
      const state = await fetchDialogue(assignedSession.experiment_session_id);
      setDialogue(state);
      setStep('dialogue');
      setSession({ ...assignedSession, status: state.status });
    } catch (dialogueError) {
      setError(userFacingError(dialogueError));
    } finally {
      setBusy(false);
    }
  }

  async function handleSendDialogueMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session || !dialogueInput.trim()) return;
    setBusy(true);
    setError('');
    try {
      await sendDialogueMessage(session.experiment_session_id, dialogueInput.trim());
      const state = await fetchDialogue(session.experiment_session_id);
      setDialogue(state);
      setDialogueInput('');
      setSession({ ...session, status: state.status });
    } catch (sendError) {
      setError(userFacingError(sendError));
    } finally {
      setBusy(false);
    }
  }

  async function handleFinishDialogue() {
    if (!session) return;
    setBusy(true);
    setError('');
    try {
      const result = await finishDialogue(session.experiment_session_id);
      setSession({ ...session, status: result.status });
      setStep('post-guide');
      setStatusMessage('你已完成 AI 对话，下面将进入后测问卷。');
    } catch (finishError) {
      setError(userFacingError(finishError));
    } finally {
      setBusy(false);
    }
  }

  function updateResponse(phase: Phase, itemKey: string, value: string | number) {
    setResponses((current) => ({
      ...current,
      [phase]: { ...current[phase], [itemKey]: value }
    }));
    setDirtyPhase(phase);
  }

  return (
    <section className="flow" aria-labelledby="participant-title">
      <FlowHeader
        eyebrow="被试端"
        title="AI 对话实验"
        description="请按页面顺序完成实验。刷新页面后，可以用同一个被试编号恢复当前阶段。"
        onBack={onBack}
      />
      {error ? <StatusNotice tone="error">{error}</StatusNotice> : null}
      {statusMessage ? <StatusNotice tone="success">{statusMessage}</StatusNotice> : null}
      {busy ? <StatusNotice tone="loading">正在处理，请稍候。</StatusNotice> : null}

      {step === 'entry' ? <ParticipantEntry onSubmit={handleEntry} busy={busy} /> : null}
      {step === 'welcome' ? (
        <StageGuide
          title="欢迎参加本实验"
          body={
            <>
              <p>本实验包含：</p>
              <ol>
                <li>前测问卷</li>
                <li>AI 对话</li>
                <li>后测问卷</li>
              </ol>
              <p>你需要使用研究者提供的被试编号进入。</p>
              <p>平台不会收集你的姓名。</p>
            </>
          }
          actionLabel="我已了解，开始"
          onAction={() => loadQuestionnaire('pre')}
          busy={busy}
        />
      ) : null}
      {step === 'pre' && questionnaire ? (
        <QuestionnairePage
          definition={questionnaire}
          responses={responses.pre}
          busy={busy}
          onChange={(itemKey, value) => updateResponse('pre', itemKey, value)}
          onSubmit={(phaseResponses) => handleQuestionnaireSubmit('pre', phaseResponses)}
        />
      ) : null}
      {step === 'ai-guide' ? (
        <StageGuide
          title="AI 对话说明"
          body={
            <>
              <p>请根据页面中的 AI 回应进行自然对话。</p>
              <p>有效完成对话需要同时满足：</p>
              <ul>
                <li>至少发送 10 条消息</li>
                <li>对话时间至少 15 分钟</li>
              </ul>
              <p>达到条件后，系统会开放“结束对话并进入后测”按钮。</p>
            </>
          }
          actionLabel="开始 AI 对话"
          onAction={handleStartDialogue}
          busy={busy}
        />
      ) : null}
      {step === 'dialogue' && dialogue ? (
        <DialoguePage
          dialogue={dialogue}
          input={dialogueInput}
          busy={busy}
          onInput={setDialogueInput}
          onSend={handleSendDialogueMessage}
          onFinish={handleFinishDialogue}
        />
      ) : null}
      {step === 'post-guide' ? (
        <StageGuide
          title="后测问卷"
          body={<p>你已完成 AI 对话，下面将进入后测问卷。请根据刚才的对话体验作答。</p>}
          actionLabel="进入后测问卷"
          onAction={() => loadQuestionnaire('post')}
          busy={busy}
        />
      ) : null}
      {step === 'post' && questionnaire ? (
        <QuestionnairePage
          definition={questionnaire}
          responses={responses.post}
          busy={busy}
          onChange={(itemKey, value) => updateResponse('post', itemKey, value)}
          onSubmit={(phaseResponses) => handleQuestionnaireSubmit('post', phaseResponses)}
        />
      ) : null}
      {step === 'complete' ? <CompletionPage /> : null}
      {step === 'blocked' ? (
        <StageGuide
          title="当前实验进度需要研究者处理"
          body={<p>此编号暂不能继续填写。请联系研究者确认后再进入实验。</p>}
          actionLabel="重新输入被试编号"
          onAction={() => setStep('entry')}
          busy={busy}
        />
      ) : null}
    </section>
  );
}

function FlowHeader({
  eyebrow,
  title,
  description,
  onBack
}: {
  eyebrow: string;
  title: string;
  description: string;
  onBack: () => void;
}) {
  return (
    <div className="flow-header">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1 id="participant-title">{title}</h1>
        <p>{description}</p>
      </div>
      <button type="button" className="text-action" onClick={onBack}>
        返回首页
      </button>
    </div>
  );
}

function ParticipantEntry({ onSubmit, busy }: { onSubmit: (event: FormEvent<HTMLFormElement>) => void; busy: boolean }) {
  return (
    <form className="entry-form" onSubmit={onSubmit}>
      <label>
        被试编号
        <input name="participant_code" autoComplete="off" required placeholder="请输入研究者提供的编号" />
      </label>
      <button type="submit" className="primary-action" disabled={busy}>
        进入实验
      </button>
    </form>
  );
}

function StageGuide({
  title,
  body,
  actionLabel,
  onAction,
  busy
}: {
  title: string;
  body: ReactNode;
  actionLabel: string;
  onAction: () => void;
  busy: boolean;
}) {
  return (
    <section className="guide-panel" aria-labelledby={`${title}-heading`}>
      <h2 id={`${title}-heading`}>{title}</h2>
      <div className="guide-body">{body}</div>
      <button type="button" className="primary-action" onClick={onAction} disabled={busy}>
        {actionLabel}
      </button>
    </section>
  );
}

function StatusNotice({ tone, children }: { tone: 'error' | 'success' | 'loading' | 'warning'; children: ReactNode }) {
  return (
    <p className={`status-notice ${tone}`} role={tone === 'error' ? 'alert' : 'status'}>
      {children}
    </p>
  );
}

type QuestionnaireGroup = {
  title: string;
  description: string;
  items: QuestionnaireItem[];
  review?: boolean;
};

function QuestionnairePage({
  definition,
  responses,
  busy,
  onChange,
  onSubmit
}: {
  definition: QuestionnaireDefinition;
  responses: Record<string, string | number>;
  busy: boolean;
  onChange: (itemKey: string, value: string | number) => void;
  onSubmit: (responses: Record<string, string | number>) => void;
}) {
  const groups = useMemo(() => buildQuestionnaireGroups(definition), [definition]);
  const [pageIndex, setPageIndex] = useState(0);
  const [localError, setLocalError] = useState('');
  const currentGroup = groups[Math.min(pageIndex, groups.length - 1)];
  const answeredRequired = definition.items.filter((item) => hasResponse(responses[item.item_key])).length;
  const requiredItems = definition.items.filter((item) => item.required);
  const missingItems = requiredItems.filter((item) => !hasResponse(responses[item.item_key]));
  const progress = Math.round(((pageIndex + 1) / groups.length) * 100);
  const phaseLabel = definition.phase === 'pre' ? '前测问卷' : '后测问卷';

  useEffect(() => {
    setPageIndex(0);
    setLocalError('');
  }, [definition.phase]);

  function goNext() {
    const missingInGroup = currentGroup.items.filter((item) => item.required && !hasResponse(responses[item.item_key]));
    if (missingInGroup.length > 0) {
      setLocalError(`本部分还有 ${missingInGroup.length} 题未完成，请完成后继续。`);
      return;
    }
    setLocalError('');
    setPageIndex((index) => Math.min(index + 1, groups.length - 1));
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (missingItems.length > 0) {
      setLocalError(`还有 ${missingItems.length} 题未完成，请返回对应部分补齐。`);
      return;
    }
    onSubmit(responses);
  }

  return (
    <section className="questionnaire" aria-labelledby="questionnaire-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">{phaseLabel} 第 {pageIndex + 1} / {groups.length} 部分</p>
          <h2 id="questionnaire-heading">{currentGroup.title}</h2>
          <p>{currentGroup.description}</p>
        </div>
        <p className="answer-count">{answeredRequired} / {requiredItems.length} 题已作答</p>
      </div>
      <div className="progress-meter" aria-label={`进度 ${progress}%`}>
        <span style={{ inlineSize: `${progress}%` }} />
      </div>
      {definition.locked ? <StatusNotice tone="success">此问卷已提交并锁定，不能自行修改。</StatusNotice> : null}
      {localError ? <StatusNotice tone="error">{localError}</StatusNotice> : null}

      <form onSubmit={handleSubmit}>
        {currentGroup.review ? (
          <ReviewSubmitPanel
            phase={definition.phase}
            missingItems={missingItems}
            locked={definition.locked}
            busy={busy}
            onJump={(item) => {
              const targetIndex = groups.findIndex((group) =>
                group.items.some((candidate) => candidate.item_key === item.item_key)
              );
              if (targetIndex >= 0) setPageIndex(targetIndex);
            }}
          />
        ) : (
          <div className="question-list">
            {currentGroup.items.map((item) => (
              <QuestionnaireItemControl
                key={item.item_key}
                item={item}
                scale={definition.scales[item.scale]}
                value={responses[item.item_key]}
                locked={definition.locked}
                onChange={(value) => onChange(item.item_key, value)}
              />
            ))}
          </div>
        )}
        <div className="form-navigation">
          <button
            type="button"
            className="secondary-action"
            disabled={pageIndex === 0 || busy}
            onClick={() => {
              setLocalError('');
              setPageIndex((index) => Math.max(index - 1, 0));
            }}
          >
            上一页
          </button>
          {pageIndex < groups.length - 1 ? (
            <button type="button" className="primary-action" onClick={goNext} disabled={busy}>
              下一页
            </button>
          ) : null}
        </div>
      </form>
    </section>
  );
}

function buildQuestionnaireGroups(definition: QuestionnaireDefinition): QuestionnaireGroup[] {
  const byInstrument = (instrument: string) => definition.items.filter((item) => item.instrument === instrument);
  if (definition.phase === 'pre') {
    return [
      {
        title: '基本信息',
        description: '请选择与你当前情况相符的选项。',
        items: byInstrument('demographics')
      },
      {
        title: '身份困扰',
        description: '请根据最近一段时间的真实感受作答。',
        items: byInstrument('identity_distress')
      },
      {
        title: '专业选择相关题项',
        description: '请围绕当前专业选择的想法作答。',
        items: definition.items.filter((item) => item.instrument === 'umics' || item.instrument === 'attention_check')
      },
      {
        title: '检查并提交',
        description: '请确认所有题目已完成。提交后将锁定，不能自行修改。',
        items: [],
        review: true
      }
    ];
  }
  return [
    {
      title: '身份困扰',
      description: '请根据刚才对话后的当前感受作答。',
      items: byInstrument('identity_distress')
    },
    {
      title: 'AI 感知能力',
      description: '请评价刚才 AI 回应给你的整体感受。',
      items: byInstrument('perceived_ai_competence')
    },
    {
      title: 'AI 拟人感',
      description: '请选择更接近你感受的一侧。',
      items: byInstrument('ai_anthropomorphism')
    },
    {
      title: '对话体验',
      description: '请根据这次 AI 对话过程作答。',
      items: byInstrument('bpnsfs_adapted_dialogue_experience')
    },
    {
      title: '专业选择相关题项',
      description: '请围绕当前专业选择的想法作答。',
      items: byInstrument('umics')
    },
    {
      title: '检查并提交',
      description: '请确认所有题目已完成。提交后将锁定，不能自行修改。',
      items: [],
      review: true
    }
  ];
}

function hasResponse(value: string | number | undefined): boolean {
  return value !== undefined && value !== null && String(value) !== '';
}

function QuestionnaireItemControl({
  item,
  scale,
  value,
  locked,
  onChange
}: {
  item: QuestionnaireItem;
  scale: ScaleProfile;
  value: string | number | undefined;
  locked: boolean;
  onChange: (value: string | number) => void;
}) {
  if (scale.value_type === 'categorical') {
    return (
      <fieldset className="question-block">
        <legend>{item.order}. {item.item_text}</legend>
        <div className="option-grid">
          {scale.options.map((option) => (
            <button
              key={option}
              type="button"
              className={value === option ? 'choice selected' : 'choice'}
              aria-pressed={value === option}
              disabled={locked}
              onClick={() => onChange(option)}
            >
              {option}
            </button>
          ))}
        </div>
      </fieldset>
    );
  }

  if (item.item_type === 'matrix_semantic_differential') {
    return <SemanticDifferentialScale item={item} scale={scale} value={value} locked={locked} onChange={onChange} />;
  }

  return <LikertScale item={item} scale={scale} value={value} locked={locked} onChange={onChange} />;
}

function LikertScale({
  item,
  scale,
  value,
  locked,
  onChange
}: {
  item: QuestionnaireItem;
  scale: ScaleProfile;
  value: string | number | undefined;
  locked: boolean;
  onChange: (value: number) => void;
}) {
  const min = scale.min_value ?? 1;
  const max = scale.max_value ?? min;
  const values = Array.from({ length: max - min + 1 }, (_, index) => min + index);
  return (
    <fieldset className="question-block">
      <legend>{item.order}. {item.item_text}</legend>
      <div className="scale-row">
        <span className="scale-anchor">{scale.labels?.[String(min)] ?? min}</span>
        <div className="scale-options" role="radiogroup" aria-label={item.item_text}>
          {values.map((option) => (
            <label key={option} className={Number(value) === option ? 'scale-choice selected' : 'scale-choice'}>
              <input
                type="radio"
                name={item.item_key}
                value={option}
                checked={Number(value) === option}
                disabled={locked}
                onChange={() => onChange(option)}
              />
              <span aria-hidden="true" />
              <em>{option}</em>
            </label>
          ))}
        </div>
        <span className="scale-anchor">{scale.labels?.[String(max)] ?? max}</span>
      </div>
    </fieldset>
  );
}

function SemanticDifferentialScale({
  item,
  scale,
  value,
  locked,
  onChange
}: {
  item: QuestionnaireItem;
  scale: ScaleProfile;
  value: string | number | undefined;
  locked: boolean;
  onChange: (value: number) => void;
}) {
  const min = scale.min_value ?? 1;
  const max = scale.max_value ?? min;
  const values = Array.from({ length: max - min + 1 }, (_, index) => min + index);
  const match = item.item_text.match(/^左：(.+?)\s*\/\s*右：(.+)$/);
  const left = match?.[1] ?? scale.labels?.[String(min)] ?? String(min);
  const right = match?.[2] ?? scale.labels?.[String(max)] ?? String(max);
  return (
    <fieldset className="question-block semantic">
      <legend>{item.order}. 请选择更接近你感受的一侧</legend>
      <div className="scale-row">
        <span className="scale-anchor">{left}</span>
        <div className="scale-options" role="radiogroup" aria-label={item.item_text}>
          {values.map((option) => (
            <label key={option} className={Number(value) === option ? 'scale-choice selected' : 'scale-choice'}>
              <input
                type="radio"
                name={item.item_key}
                value={option}
                checked={Number(value) === option}
                disabled={locked}
                onChange={() => onChange(option)}
              />
              <span aria-hidden="true" />
              <em>{option}</em>
            </label>
          ))}
        </div>
        <span className="scale-anchor">{right}</span>
      </div>
    </fieldset>
  );
}

function ReviewSubmitPanel({
  phase,
  missingItems,
  locked,
  busy,
  onJump
}: {
  phase: Phase;
  missingItems: QuestionnaireItem[];
  locked: boolean;
  busy: boolean;
  onJump: (item: QuestionnaireItem) => void;
}) {
  return (
    <div className="review-panel">
      <p>请确认所有题目已完成。提交后将锁定，不能自行修改。</p>
      {missingItems.length > 0 ? (
        <div className="missing-list">
          <p>未完成题目：</p>
          {missingItems.slice(0, 8).map((item) => (
            <button key={item.item_key} type="button" className="text-action" onClick={() => onJump(item)}>
              第 {item.order} 题
            </button>
          ))}
          {missingItems.length > 8 ? <span>另有 {missingItems.length - 8} 题未完成</span> : null}
        </div>
      ) : (
        <StatusNotice tone="success">所有必答题已完成，可以提交。</StatusNotice>
      )}
      <button type="submit" className="primary-action" disabled={locked || busy || missingItems.length > 0}>
        提交{phase === 'pre' ? '前测' : '后测'}
      </button>
    </div>
  );
}

function DialoguePage({
  dialogue,
  input,
  busy,
  onInput,
  onSend,
  onFinish
}: {
  dialogue: DialogueState;
  input: string;
  busy: boolean;
  onInput: (value: string) => void;
  onSend: (event: FormEvent<HTMLFormElement>) => void;
  onFinish: () => void;
}) {
  const progress = dialogue.progress;
  const elapsed = formatDuration(progress.dialogue_elapsed_seconds);
  const required = formatDuration(progress.required_elapsed_seconds);
  return (
    <section className="dialogue-layout" aria-labelledby="dialogue-heading">
      <div className="section-heading">
        <div>
          <p className="eyebrow">AI 对话</p>
          <h2 id="dialogue-heading">请自然完成本阶段对话</h2>
          <p>完成资格由平台规则判断，不是由 AI 批准。</p>
        </div>
      </div>
      <div className="dialogue-progress" aria-label="完成要求">
        <h3>完成要求</h3>
        <p>消息数：{Math.min(progress.participant_turn_count, progress.required_participant_turns)} / {progress.required_participant_turns}</p>
        <p>对话时长：{elapsed} / {required}</p>
        <p>当前状态：{progress.eligible_to_finish ? '已达到完成条件' : '尚未达到完成条件'}</p>
      </div>
      <div className="chat-window" aria-live="polite">
        {dialogue.messages.length === 0 ? (
          <p className="empty-state">AI 对话开始后，消息会显示在这里。</p>
        ) : (
          dialogue.messages.map((message) => (
            <article
              key={message.id}
              className={message.role === 'participant' ? 'message participant' : 'message assistant'}
            >
              <p className="message-role">{message.role === 'participant' ? '我' : 'AI'}</p>
              <MarkdownContent text={message.content} />
            </article>
          ))
        )}
      </div>
      <form className="chat-form" onSubmit={onSend}>
        <label>
          对话内容
          <textarea
            value={input}
            onChange={(event) => onInput(event.target.value)}
            placeholder="请输入你想发送给 AI 的内容"
            rows={3}
          />
        </label>
        <button type="submit" className="primary-action" disabled={busy || !input.trim()}>
          发送
        </button>
      </form>
      <button type="button" className="primary-action" disabled={!progress.eligible_to_finish || busy} onClick={onFinish}>
        {progress.eligible_to_finish ? '结束对话并进入后测' : '尚未达到完成条件，暂不能进入后测'}
      </button>
    </section>
  );
}

function MarkdownContent({ text }: { text: string }) {
  const lines = text.split(/\r?\n/);
  const nodes: ReactNode[] = [];
  let bullets: string[] = [];

  function flushBullets() {
    if (bullets.length === 0) return;
    nodes.push(
      <ul key={`list-${nodes.length}`}>
        {bullets.map((line, index) => (
          <li key={`${line}-${index}`}>{parseInlineMarkdown(line)}</li>
        ))}
      </ul>
    );
    bullets = [];
  }

  lines.forEach((line, index) => {
    const trimmed = line.trim();
    if (!trimmed) {
      flushBullets();
      return;
    }
    if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      bullets.push(trimmed.slice(2));
      return;
    }
    flushBullets();
    nodes.push(<p key={`p-${index}`}>{parseInlineMarkdown(trimmed.replace(/^#{1,3}\s*/, ''))}</p>);
  });
  flushBullets();

  return <div className="markdown-content">{nodes}</div>;
}

function parseInlineMarkdown(text: string): ReactNode[] {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).filter(Boolean);
  return parts.map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return <code key={index}>{part.slice(1, -1)}</code>;
    }
    return part;
  });
}

function CompletionPage() {
  return (
    <section className="guide-panel completion" aria-labelledby="completion-heading">
      <p className="eyebrow">实验完成</p>
      <h2 id="completion-heading">感谢参与</h2>
      <p>你已完成前测问卷、AI 对话和后测问卷。本编号的问卷提交已锁定，不能重复提交。</p>
    </section>
  );
}

type PendingAction =
  | { kind: 'reset'; row: AdminStatusRow }
  | { kind: 'exclude'; row: AdminStatusRow }
  | { kind: 'export' }
  | null;

function AdminFlow({ onBack }: { onBack: () => void }) {
  const [token, setToken] = useState('');
  const [statusRows, setStatusRows] = useState<AdminStatusRow[]>([]);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [pendingAction, setPendingAction] = useState<PendingAction>(null);

  async function refreshStatus(currentToken = token) {
    if (!currentToken) return;
    const status = await fetchAdminStatus(currentToken);
    setStatusRows(status.participants);
  }

  async function handleLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy(true);
    setError('');
    try {
      const login = await adminLogin(String(data.get('username') ?? ''), String(data.get('password') ?? ''));
      setToken(login.token);
      await refreshStatus(login.token);
      setMessage('研究者已登录。');
    } catch (loginError) {
      setError(userFacingError(loginError));
    } finally {
      setBusy(false);
    }
  }

  async function handleImport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setBusy(true);
    setError('');
    try {
      const participantCode = String(data.get('participant_code') ?? '').trim();
      const assignedGroup = String(data.get('assigned_group') ?? '');
      const result = await importParticipants(token, [
        { participant_code: participantCode, assigned_group: assignedGroup || undefined }
      ]);
      setMessage(`已导入 ${result.imported_count} 个被试编号。`);
      event.currentTarget.reset();
      await refreshStatus();
    } catch (importError) {
      setError(userFacingError(importError));
    } finally {
      setBusy(false);
    }
  }

  async function confirmAction(reason: string) {
    if (!pendingAction) return;
    setBusy(true);
    setError('');
    try {
      if (pendingAction.kind === 'reset' && pendingAction.row.experiment_session_id) {
        await resetPreSurvey(token, pendingAction.row.experiment_session_id, reason);
        setMessage(`已重置 ${pendingAction.row.participant_code} 的前测，原因已记录。`);
      }
      if (pendingAction.kind === 'exclude' && pendingAction.row.experiment_session_id) {
        await markSessionExcluded(token, pendingAction.row.experiment_session_id, reason);
        setMessage(`已排除 ${pendingAction.row.participant_code}，原因已记录。`);
      }
      if (pendingAction.kind === 'export') {
        const blob = await exportPackage(token);
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `mentor-echo-export-${new Date().toISOString().replace(/[:.]/g, '-')}.zip`;
        link.click();
        URL.revokeObjectURL(url);
        setMessage('导出 ZIP 已生成。请按敏感数据流程保存和传递。');
      }
      setPendingAction(null);
      await refreshStatus();
    } catch (actionError) {
      setError(userFacingError(actionError));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="flow admin-flow" aria-labelledby="admin-title">
      <FlowHeader
        eyebrow="研究者管理端"
        title="试点管理后台"
        description="登录后可导入编号、查看进度、执行重置或排除，并导出研究数据。"
        onBack={onBack}
      />
      {error ? <StatusNotice tone="error">{error}</StatusNotice> : null}
      {message ? <StatusNotice tone="success">{message}</StatusNotice> : null}
      {busy ? <StatusNotice tone="loading">正在处理，请稍候。</StatusNotice> : null}

      {!token ? (
        <form className="entry-form admin-login" onSubmit={handleLogin}>
          <label>
            研究者账号
            <input name="username" required defaultValue="researcher" autoComplete="username" />
          </label>
          <label>
            研究者密码
            <input name="password" required type="password" autoComplete="current-password" />
          </label>
          <button type="submit" className="primary-action" disabled={busy}>
            登录管理后台
          </button>
        </form>
      ) : (
        <>
          <ParticipantImportPanel onImport={handleImport} busy={busy} onRefresh={() => refreshStatus()} />
          <AdminDashboard
            rows={statusRows}
            busy={busy}
            onRefresh={() => refreshStatus()}
            onReset={(row) => setPendingAction({ kind: 'reset', row })}
            onExclude={(row) => setPendingAction({ kind: 'exclude', row })}
            onExport={() => setPendingAction({ kind: 'export' })}
          />
        </>
      )}
      {pendingAction ? (
        <SessionActionModal
          action={pendingAction}
          busy={busy}
          onCancel={() => setPendingAction(null)}
          onConfirm={confirmAction}
        />
      ) : null}
    </section>
  );
}

function ParticipantImportPanel({
  onImport,
  busy,
  onRefresh
}: {
  onImport: (event: FormEvent<HTMLFormElement>) => void;
  busy: boolean;
  onRefresh: () => void;
}) {
  return (
    <section className="management-section" aria-labelledby="import-heading">
      <div className="section-heading">
        <div>
          <h2 id="import-heading">导入被试编号</h2>
          <p>仅导入匿名编号。分组可留空，由平台在被试进入分组点时随机确定。</p>
        </div>
        <button type="button" className="secondary-action" onClick={onRefresh} disabled={busy}>
          刷新仪表盘
        </button>
      </div>
      <form className="row-form" onSubmit={onImport}>
        <label>
          被试编号
          <input name="participant_code" required placeholder="例如 PILOT001" />
        </label>
        <label>
          预设分组
          <select name="assigned_group" defaultValue="">
            <option value="">首次进入时随机</option>
            <option value="experiment">实验组</option>
            <option value="control">控制组</option>
          </select>
        </label>
        <button type="submit" className="primary-action" disabled={busy}>
          导入
        </button>
      </form>
    </section>
  );
}

function AdminDashboard({
  rows,
  busy,
  onRefresh,
  onReset,
  onExclude,
  onExport
}: {
  rows: AdminStatusRow[];
  busy: boolean;
  onRefresh: () => void;
  onReset: (row: AdminStatusRow) => void;
  onExclude: (row: AdminStatusRow) => void;
  onExport: () => void;
}) {
  const summary = useMemo(
    () => [
      { label: '总被试数', value: rows.length },
      { label: '未开始', value: rows.filter((row) => row.status === 'not_started').length },
      { label: '前测完成', value: rows.filter((row) => row.pre_survey_submitted).length },
      {
        label: '对话中',
        value: rows.filter((row) => row.status === 'chat_in_progress' || row.status === 'chat_eligible_to_finish').length
      },
      { label: '已完成', value: rows.filter((row) => row.completed).length },
      { label: '已排除', value: rows.filter((row) => row.excluded).length }
    ],
    [rows]
  );

  return (
    <section className="management-section" aria-labelledby="dashboard-heading">
      <div className="section-heading">
        <div>
          <h2 id="dashboard-heading">试点进度仪表盘</h2>
          <p>默认只显示进度、分组和操作指标，不内联展示完整原始聊天。</p>
        </div>
        <div className="toolbar">
          <button type="button" className="secondary-action" onClick={onRefresh} disabled={busy}>
            刷新
          </button>
          <button type="button" className="primary-action" onClick={onExport} disabled={busy}>
            导出 ZIP
          </button>
        </div>
      </div>
      <div className="summary-grid">
        {summary.map((item) => (
          <article key={item.label} className="summary-card">
            <p>{item.label}</p>
            <strong>{item.value}</strong>
          </article>
        ))}
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>被试编号</th>
              <th>分组</th>
              <th>来源</th>
              <th>状态</th>
              <th>前测</th>
              <th>对话轮次</th>
              <th>对话时长</th>
              <th>后测</th>
              <th>排除</th>
              <th>最后访问</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={11}>暂无被试记录。导入编号后会显示在这里。</td>
              </tr>
            ) : (
              rows.map((row) => (
                <tr key={row.participant_code}>
                  <td>{row.participant_code}</td>
                  <td>{labelFor(groupLabels, row.group)}</td>
                  <td>{labelFor(sourceLabels, row.assignment_source)}</td>
                  <td>{labelFor(statusLabels, row.status)}</td>
                  <td>{row.pre_survey_submitted ? '已提交' : '未提交'}</td>
                  <td>{row.participant_turn_count}</td>
                  <td>{formatDuration(row.dialogue_elapsed_seconds)}</td>
                  <td>{row.post_survey_submitted ? '已提交' : '未提交'}</td>
                  <td>{row.excluded ? `已排除：${row.exclusion_reason ?? '未填写原因'}` : '纳入'}</td>
                  <td>{row.last_seen_at ? new Date(row.last_seen_at).toLocaleString() : '暂无'}</td>
                  <td>
                    <div className="table-actions">
                      <button
                        type="button"
                        className="secondary-action"
                        disabled={!row.experiment_session_id || busy}
                        onClick={() => onReset(row)}
                      >
                        重置
                      </button>
                      <button
                        type="button"
                        className="danger-action"
                        disabled={!row.experiment_session_id || row.excluded || busy}
                        onClick={() => onExclude(row)}
                      >
                        排除
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function SessionActionModal({
  action,
  busy,
  onCancel,
  onConfirm
}: {
  action: NonNullable<PendingAction>;
  busy: boolean;
  onCancel: () => void;
  onConfirm: (reason: string) => void;
}) {
  const [reason, setReason] = useState('');
  const [acknowledged, setAcknowledged] = useState(false);
  const isExport = action.kind === 'export';
  const title =
    action.kind === 'reset'
      ? `重置 ${action.row.participant_code} 的前测`
      : action.kind === 'exclude'
        ? `排除 ${action.row.participant_code}`
        : '导出研究数据 ZIP';

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onConfirm(isExport ? 'confirmed_sensitive_export' : reason.trim());
  }

  return (
    <div className="modal-backdrop" role="presentation">
      <form className="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title" onSubmit={handleSubmit}>
        <h2 id="modal-title">{title}</h2>
        {action.kind === 'reset' ? (
          <p>重置会重新开放前测填写入口。请填写审计原因，便于后续追踪。</p>
        ) : null}
        {action.kind === 'exclude' ? (
          <p>排除会将该会话从常规分析中标记出来，但不会删除原始记录。请填写排除原因。</p>
        ) : null}
        {isExport ? (
          <div className="warning-block">
            <p>ZIP 导出包包含敏感原始聊天文件 `chat_messages.jsonl`。</p>
            <p>仪表盘不会内联展示完整原始聊天，导出后请按研究数据安全流程保存。</p>
            <label className="checkbox-line">
              <input type="checkbox" checked={acknowledged} onChange={(event) => setAcknowledged(event.target.checked)} />
              我已了解导出包包含敏感原始聊天
            </label>
          </div>
        ) : (
          <label>
            原因
            <textarea
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              required
              rows={4}
              placeholder="请填写可审计的原因"
            />
          </label>
        )}
        <div className="modal-actions">
          <button type="button" className="secondary-action" onClick={onCancel} disabled={busy}>
            取消
          </button>
          <button type="submit" className={action.kind === 'exclude' ? 'danger-action' : 'primary-action'} disabled={busy || (isExport ? !acknowledged : !reason.trim())}>
            确认
          </button>
        </div>
      </form>
    </div>
  );
}

export default App;
