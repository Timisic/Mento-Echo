import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import App from '../src/App';

const runRealApiSmoke = import.meta.env.VITE_REAL_API_SMOKE === '1';
const maybeDescribe = runRealApiSmoke ? describe : describe.skip;

maybeDescribe('应用真实 API 冒烟行为', () => {
  it('被试首页不暴露后端和数据库健康状态', async () => {
    render(<App />);

    await waitFor(
      () => {
        expect(screen.getByRole('heading', { name: 'Mentor Echo AI 对话实验平台' })).toBeInTheDocument();
        expect(screen.queryByTestId('health-status')).not.toBeInTheDocument();
        expect(screen.queryByText(/后端|数据库/)).not.toBeInTheDocument();
      },
      { timeout: 5000 }
    );
  });
});
