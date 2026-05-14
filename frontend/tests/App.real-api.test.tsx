import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import App from '../src/App';

const runRealApiSmoke = import.meta.env.VITE_REAL_API_SMOKE === '1';
const maybeDescribe = runRealApiSmoke ? describe : describe.skip;

maybeDescribe('App real API smoke behavior', () => {
  it('renders backend and database health from a live FastAPI API call', async () => {
    render(<App />);

    await waitFor(
      () => {
        expect(screen.getByTestId('health-status')).toHaveTextContent('Backend ok; database ok');
      },
      { timeout: 5000 }
    );
  });
});
