import { render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../src/App';

describe('App API smoke behavior', () => {
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

  it('renders backend and database health from the API', async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId('health-status')).toHaveTextContent('Backend ok; database ok');
    });
    expect(fetch).toHaveBeenCalledWith('http://localhost:8000/api/health', expect.any(Object));
  });
});
