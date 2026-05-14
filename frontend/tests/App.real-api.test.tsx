import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import App from '../src/App';

const runRealApiSmoke = import.meta.env.VITE_REAL_API_SMOKE === '1';
const maybeDescribe = runRealApiSmoke ? describe : describe.skip;

maybeDescribe('应用真实 API 冒烟行为', () => {
  it('从实时 FastAPI 调用渲染后端和数据库健康状态', async () => {
    render(<App />);

    await waitFor(
      () => {
        expect(screen.getByTestId('health-status')).toHaveTextContent('后端 ok；数据库正常');
      },
      { timeout: 5000 }
    );
  });
});
