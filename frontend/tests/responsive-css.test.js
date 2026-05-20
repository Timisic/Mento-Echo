import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

describe('chat responsive CSS contract', () => {
  const css = readFileSync(join(process.cwd(), 'src/styles.css'), 'utf8');

  it('prevents horizontal chat overflow and keeps the mobile composer reachable', () => {
    expect(css).toContain('overflow-x: clip');
    expect(css).toContain('overflow-x: hidden');
    expect(css).toContain('overscroll-behavior: contain');
    expect(css).toContain('position: sticky');
    expect(css).toContain('env(safe-area-inset-bottom)');
  });

  it('uses a phone-first single-column chat layout below tablet width', () => {
    expect(css).toContain('@media (max-width: 900px)');
    expect(css).toContain('grid-template-columns: 1fr');
    expect(css).toContain('order: -1');
    expect(css).toContain('@media (max-width: 640px)');
  });
});
