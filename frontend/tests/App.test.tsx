import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../src/App';

const baseUrl = 'http://localhost:8000';
const scrollIntoViewMock = vi.fn();

const session = {
  experiment_session_id: 'session-1',
  participant_code: 'PILOT001',
  status: 'not_started',
  group: null,
  assignment_source: null,
  assignment_locked: false,
  resume_count: 0,
  last_seen_at: '2026-05-16T05:00:00Z',
  started_at: '2026-05-16T05:00:00Z',
  completed_at: null
};

const preQuestionnaire = {
  questionnaire_version: 'mentor_echo_questionnaire_v2026_05_25_major_grade_injection',
  phase: 'pre',
  locked: false,
  items: [
    {
      phase: 'pre',
      order: 1,
      item_key: 'pre_demo_gender',
      item_text: '您的性别',
      item_type: 'single_choice',
      scale: 'gender_options',
      instrument: 'demographics',
      dimension: 'gender',
      reverse_scored: false,
      required: true,
      attention_check: false
    },
    {
      phase: 'pre',
      order: 2,
      item_key: 'pre_demo_grade',
      item_text: '您目前在读：',
      item_type: 'single_choice',
      scale: 'grade_options',
      instrument: 'demographics',
      dimension: 'grade',
      reverse_scored: false,
      required: true,
      attention_check: false
    },
    {
      phase: 'pre',
      order: 3,
      item_key: 'pre_demo_major',
      item_text: '您的专业',
      item_type: 'text_input',
      scale: 'major_text',
      instrument: 'demographics',
      dimension: 'major',
      reverse_scored: false,
      required: true,
      attention_check: false
    },
    {
      phase: 'pre',
      order: 4,
      item_key: 'pre_demo_age',
      item_text: '您的年龄',
      item_type: 'number_input',
      scale: 'age_years',
      instrument: 'demographics',
      dimension: 'age',
      reverse_scored: false,
      required: true,
      attention_check: false
    },
    {
      phase: 'pre',
      order: 5,
      item_key: 'pre_identity_distress_01',
      item_text: '我会因为未来发展方向不清楚而感到困扰。',
      item_type: 'matrix_single_choice',
      scale: 'identity_distress_1_5',
      instrument: 'identity_distress',
      dimension: 'total',
      reverse_scored: false,
      required: true,
      attention_check: false
    },
    {
      phase: 'pre',
      order: 6,
      item_key: 'pre_ac_umics_select_5',
      item_text: '这道题请选择5',
      item_type: 'matrix_single_choice',
      scale: 'agreement_1_5',
      instrument: 'attention_check',
      dimension: 'umics_attention',
      reverse_scored: false,
      required: true,
      attention_check: true
    }
  ],
  scales: {
    gender_options: {
      key: 'gender_options',
      value_type: 'categorical',
      min_value: null,
      max_value: null,
      labels: null,
      options: ['男', '女']
    },
    grade_options: {
      key: 'grade_options',
      value_type: 'categorical',
      min_value: null,
      max_value: null,
      labels: null,
      options: ['大一', '大二', '大三', '大四', '硕士研究生', '博士研究生']
    },
    major_text: {
      key: 'major_text',
      value_type: 'text',
      min_value: null,
      max_value: null,
      labels: null,
      options: []
    },
    age_years: {
      key: 'age_years',
      value_type: 'integer',
      min_value: 16,
      max_value: 60,
      labels: { '16': '16岁', '60': '60岁' },
      options: []
    },
    identity_distress_1_5: {
      key: 'identity_distress_1_5',
      value_type: 'integer',
      min_value: 1,
      max_value: 5,
      labels: { '1': '完全没有', '5': '非常严重' },
      options: []
    },
    agreement_1_5: {
      key: 'agreement_1_5',
      value_type: 'integer',
      min_value: 1,
      max_value: 5,
      labels: { '1': '完全不符合', '5': '完全符合' },
      options: []
    }
  }
};

const dialogueState = {
  experiment_session_id: 'session-1',
  participant_code: 'PILOT001',
  group: 'experiment',
  system_prompt_version: null,
  status: 'chat_in_progress',
  initial_message_suggestion: null,
  progress: {
    participant_turn_count: 3,
    dialogue_elapsed_seconds: 261,
    met_min_turns: false,
    met_min_duration: false,
    eligible_to_finish: false,
    required_participant_turns: 6,
    required_elapsed_seconds: 600,
    max_participant_turns: 12,
    max_elapsed_seconds: 3600,
    finish_prompt_visible: false,
    forced_to_finish: false,
    forced_finish_reason: null,
    finish_decision: null,
    continue_until_turn_count: null,
    reminder_due: true,
    reminder_text: '请继续围绕专业选择与未来方向交流。'
  },
  messages: [
    {
      id: 'message-1',
      message_index: 1,
      role: 'assistant',
      content:
        '**你好**，请从你愿意分享的内容开始。\n这是一行补充说明。\n\n- 列出一个想法\n1. 再补充一个步骤\n\n可以参考[资料](https://example.com/guide)，不要打开[危险](javascript:alert(1))。\n\n```ts\nconst choice = \"major\";\n```\n\n<script>alert(\"xss\")</script>',
      provider_name: null,
      model_name: null,
      system_prompt_version: null,
      generation_params: null,
      duration_ms: 12,
      retry_count: 0,
      error_code: null,
      error_message_sanitized: null,
      created_at: '2026-05-16T05:01:00Z'
    }
  ]
};

const adminRow = {
  participant_code: 'PILOT001',
  assigned_group_imported: 'experiment',
  experiment_session_id: 'session-1',
  status: 'chat_in_progress',
  group: 'experiment',
  assignment_source: 'imported',
  assignment_locked: true,
  started_at: '2026-05-16T05:00:00Z',
  pre_survey_submitted_at: '2026-05-16T05:05:00Z',
  chat_started_at: '2026-05-16T05:06:00Z',
  chat_completed_at: null,
  post_survey_submitted_at: null,
  completed_at: null,
  pre_survey_submitted: true,
  post_survey_submitted: false,
  participant_turn_count: 3,
  dialogue_elapsed_seconds: 261,
  dialogue_elapsed_minutes: 4.35,
  met_min_turns: false,
  met_min_duration: false,
  dialogue_completion_eligible: false,
  dialogue_completed: false,
  completed: false,
  excluded: false,
  exclusion_reason: null,
  topic_off_track_ratio: null,
  topic_off_track_gt_30pct: null,
  topic_validity_status: 'pending_manual_coding',
  topic_validity_notes: null,
  topic_validity_coded_at: null,
  resume_count: 1,
  last_seen_at: '2026-05-16T05:07:00Z'
};

function jsonResponse(body: unknown) {
  return Promise.resolve({
    ok: true,
    json: async () => body,
    text: async () => JSON.stringify(body),
    blob: async () => new Blob(['zip'])
  } as Response);
}

function errorResponse(detail: unknown, status = 500) {
  return Promise.resolve({
    ok: false,
    status,
    json: async () => ({ detail }),
    text: async () => JSON.stringify({ detail })
  } as Response);
}

describe('Mentor Echo 前端 UI', () => {
  beforeEach(() => {
    scrollIntoViewMock.mockClear();
    Object.defineProperty(Element.prototype, 'scrollIntoView', {
      configurable: true,
      value: scrollIntoViewMock
    });
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn(() => 'blob:export'),
      revokeObjectURL: vi.fn()
    });
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => undefined);
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('先展示角色入口，而不是同屏暴露所有操作', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ app: 'ok', database: { ok: true } }),
        text: async () => ''
      })
    );

    render(<App />);

    expect(screen.getByRole('heading', { name: 'Mentor Echo AI 对话实验平台' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '我是被试，进入实验' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '我是研究者，进入管理后台' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '导出 ZIP' })).not.toBeInTheDocument();
    expect(screen.queryByTestId('health-status')).not.toBeInTheDocument();
    expect(screen.queryByText(/后端|数据库/)).not.toBeInTheDocument();
  });

  it('被试路径隐藏内部字段，并用问卷和对话进度推进', async () => {
    let resolveSendMessage: ((value: Response) => void) | undefined;
    const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input).replace(baseUrl, '');
      if (url === '/api/health') return jsonResponse({ app: 'ok', database: { ok: true } });
      if (url === '/api/participant/entry') return jsonResponse({ accepted: true, message: 'ok', session });
      if (url === '/api/participant/sessions/session-1/questionnaires/pre') return jsonResponse(preQuestionnaire);
      if (url === '/api/participant/sessions/session-1/questionnaires/pre/submit') {
        expect(String(init?.body)).toContain('pre_demo_gender');
        return jsonResponse({
          phase: 'pre',
          questionnaire_version: preQuestionnaire.questionnaire_version,
          locked: true,
          response_count: 6,
          scores: [],
          session: { ...session, status: 'pre_survey_submitted' }
        });
      }
      if (url === '/api/participant/sessions/session-1/assignment') {
        return jsonResponse({
          experiment_session_id: 'session-1',
          participant_code: 'PILOT001',
          group: 'experiment',
          assignment_source: 'imported',
          assignment_locked: true
        });
      }
      if (url === '/api/participant/sessions/session-1/dialogue') return jsonResponse(dialogueState);
      if (url === '/api/participant/sessions/session-1/dialogue/messages') {
        return new Promise<Response>((resolve) => {
          resolveSendMessage = resolve;
        });
      }
      return Promise.reject(new Error(`Unexpected request ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    const { container } = render(<App />);

    fireEvent.click(screen.getByRole('button', { name: '我是被试，进入实验' }));
    fireEvent.change(screen.getByLabelText('被试编号'), { target: { value: 'PILOT001' } });
    fireEvent.click(screen.getByRole('button', { name: '进入实验' }));

    expect(await screen.findByRole('heading', { name: '欢迎参加本实验' })).toBeInTheDocument();
    expect(screen.queryByText('session-1')).not.toBeInTheDocument();
    expect(screen.queryByText('实验组')).not.toBeInTheDocument();
    expect(screen.queryByText('导入指定')).not.toBeInTheDocument();
    expect(screen.queryByText(/研究一|预实验|分组|grouped|prompt|provider|thread|turn/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '我已了解，开始' }));
    expect(await screen.findByRole('heading', { name: '基本信息' })).toBeInTheDocument();
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '男' }));
    fireEvent.click(screen.getByRole('button', { name: '大三' }));
    fireEvent.change(screen.getByPlaceholderText('请输入你的专业'), { target: { value: '计算机科学与技术' } });
    fireEvent.change(screen.getByPlaceholderText('请输入年龄'), { target: { value: '20' } });
    scrollIntoViewMock.mockClear();
    fireEvent.click(screen.getByRole('button', { name: '下一页' }));

    expect(await screen.findByRole('heading', { name: '身份困扰' })).toBeInTheDocument();
    expect(scrollIntoViewMock).toHaveBeenCalledWith({ block: 'start', inline: 'nearest' });
    fireEvent.click(screen.getAllByRole('radio')[2]);
    fireEvent.click(screen.getByRole('button', { name: '下一页' }));

    expect(await screen.findByRole('heading', { name: '专业选择相关题项' })).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole('radio')[4]);
    fireEvent.click(screen.getByRole('button', { name: '下一页' }));
    fireEvent.click(screen.getByRole('button', { name: '提交前测' }));

    expect(await screen.findByRole('heading', { name: 'AI 对话说明' })).toBeInTheDocument();
    expect(screen.getByText('至少 6 个有效用户回合')).toBeInTheDocument();
    expect(screen.getByText('对话时间至少 10 分钟')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '开始 AI 对话' }));

    expect(await screen.findByRole('heading', { name: '围绕专业与未来方向展开对话' })).toBeInTheDocument();
    expect(screen.queryByText('专业选择与未来升学/就业方向')).not.toBeInTheDocument();
    expect(container.querySelector('.topic-banner')).toBeNull();
    expect(await screen.findByText('请继续围绕专业选择与未来方向交流。')).toBeInTheDocument();
    expect(screen.queryByText('请确认接下来的提问仍围绕专业选择、未来方向、升学或就业展开。')).not.toBeInTheDocument();
    expect(screen.getByText('消息数：3 / 6')).toBeInTheDocument();
    expect(screen.getByText('对话时长：04:21 / 10:00')).toBeInTheDocument();
    expect(screen.queryByText('60 分钟后页面会提示可以休息退出；后端不会因时间到达而强制结束。')).not.toBeInTheDocument();
    expect(screen.queryByText(/上限：.*60:00/)).not.toBeInTheDocument();
    expect(screen.getByText('尚未达到完成条件')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '暂不能进入后测' })).toBeDisabled();
    expect(screen.queryByText('major_choice_dialogue_protocol_v2')).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: '资料' })).toHaveAttribute('href', 'https://example.com/guide');
    expect(screen.queryByRole('link', { name: '危险' })).not.toBeInTheDocument();
    expect(container.querySelector('.markdown-content p br')).not.toBeNull();
    expect(container.querySelector('.markdown-content pre code')?.textContent).toBe('const choice = "major";');
    expect(container.querySelector('.markdown-content script')).toBeNull();
    expect(screen.queryByText('experiment_identity_dialogue_v1')).not.toBeInTheDocument();
    expect(screen.queryByText('mock-model')).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('对话内容'), { target: { value: '我在想是否继续读当前专业。' } });
    fireEvent.click(screen.getByRole('button', { name: '发送' }));

    expect(await screen.findByText('我在想是否继续读当前专业。')).toBeInTheDocument();
    expect(screen.getByLabelText('对话内容')).toHaveValue('');
    expect(screen.getByLabelText('正在生成回复')).toBeInTheDocument();
    expect(screen.queryByText('正在处理，请稍候。')).not.toBeInTheDocument();

    resolveSendMessage?.(
      {
        ok: true,
        json: async () => ({ progress: dialogueState.progress, status: 'chat_in_progress' }),
        text: async () => ''
      } as Response
    );
  });

  it('对话主题提醒短暂显示后自动收起，不占用聊天布局空间', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const activeSession = {
      ...session,
      status: 'chat_in_progress',
      group: 'pilot',
      assignment_source: 'pilot_single',
      assignment_locked: true
    };
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input).replace(baseUrl, '');
      if (url === '/api/health') return jsonResponse({ app: 'ok', database: { ok: true } });
      if (url === '/api/participant/entry') return jsonResponse({ accepted: true, message: 'ok', session: activeSession });
      if (url === '/api/participant/sessions/session-1/dialogue') return jsonResponse(dialogueState);
      return Promise.reject(new Error(`Unexpected request ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    const { container } = render(<App />);

    fireEvent.click(screen.getByRole('button', { name: '我是被试，进入实验' }));
    fireEvent.change(screen.getByLabelText('被试编号'), { target: { value: 'PILOT001' } });
    fireEvent.click(screen.getByRole('button', { name: '进入实验' }));

    expect(await screen.findByText('请继续围绕专业选择与未来方向交流。')).toBeInTheDocument();
    expect(container.querySelector('.chat-panel > .topic-reminder')).not.toBeNull();
    expect(container.querySelector('.dialogue-layout > .topic-reminder')).toBeNull();

    act(() => {
      vi.advanceTimersByTime(30000);
    });

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(`${baseUrl}/api/participant/sessions/session-1/dialogue`, expect.any(Object));
    });

    act(() => {
      vi.advanceTimersByTime(4600);
    });

    await waitFor(() => {
      expect(screen.queryByText('请继续围绕专业选择与未来方向交流。')).not.toBeInTheDocument();
    });
    expect(container.querySelector('.topic-banner')).toBeNull();
  });

  it('未知服务端错误不会把内部实现文本显示给被试', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input).replace(baseUrl, '');
      if (url === '/api/health') return jsonResponse({ app: 'ok', database: { ok: true } });
      if (url === '/api/participant/entry') {
        return errorResponse('provider thread_id failed in grouped prompt mode');
      }
      return Promise.reject(new Error(`Unexpected request ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);

    fireEvent.click(screen.getByRole('button', { name: '我是被试，进入实验' }));
    fireEvent.change(screen.getByLabelText('被试编号'), { target: { value: 'PILOT001' } });
    fireEvent.click(screen.getByRole('button', { name: '进入实验' }));

    expect(await screen.findByText('操作失败，请稍后重试或联系研究者。')).toBeInTheDocument();
    expect(screen.queryByText(/provider|thread_id|grouped|prompt/)).not.toBeInTheDocument();
  });

  it('研究者登录后显示仪表盘，并在导出前提示敏感原始聊天', async () => {
    const fetchMock = vi.fn((input: RequestInfo | URL) => {
      const url = String(input).replace(baseUrl, '');
      if (url === '/api/health') return jsonResponse({ app: 'ok', database: { ok: true } });
      if (url === '/api/admin/login') return jsonResponse({ token: 'admin-token', token_type: 'bearer' });
      if (url === '/api/admin/status') return jsonResponse({ participants: [adminRow] });
      if (url === '/api/admin/export') return jsonResponse({});
      return Promise.reject(new Error(`Unexpected request ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<App />);

    fireEvent.click(screen.getByRole('button', { name: '我是研究者，进入管理后台' }));
    expect(screen.getByRole('heading', { name: '管理后台' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: '导入被试编号' })).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('研究者密码'), { target: { value: 'change-me-admin-password' } });
    fireEvent.click(screen.getByRole('button', { name: '登录管理后台' }));

    expect(await screen.findByRole('heading', { name: '进度仪表盘' })).toBeInTheDocument();
    expect(screen.getByText('总被试数')).toBeInTheDocument();
    expect(screen.getByText('PILOT001')).toBeInTheDocument();
    expect(screen.queryByLabelText('预设分组')).not.toBeInTheDocument();
    expect(screen.queryByText('完整原始聊天内容')).not.toBeInTheDocument();
    expect(screen.queryByText(/研究一|预实验|预设分组|实验组|控制组|grouped/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '导出 ZIP' }));
    expect(await screen.findByRole('dialog')).toHaveTextContent('chat_messages.jsonl');
    expect(screen.getByRole('button', { name: '确认' })).toBeDisabled();
    fireEvent.click(screen.getByLabelText('我已了解导出包包含敏感原始聊天'));
    fireEvent.click(screen.getByRole('button', { name: '确认' }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(`${baseUrl}/api/admin/export`, expect.any(Object));
    });
  });
});
