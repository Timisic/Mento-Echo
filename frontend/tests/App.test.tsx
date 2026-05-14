import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../src/App';

describe('应用 API 冒烟行为', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ app: 'ok', database: { ok: true } })
      })
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('从 API 渲染后端和数据库健康状态', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId('health-status')).toHaveTextContent('后端 ok；数据库正常');
    });
    expect(fetch).toHaveBeenCalledWith('http://localhost:8000/api/health', expect.any(Object));
  });
});
