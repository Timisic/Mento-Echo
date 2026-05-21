import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

function blockAfter(source, startIndex) {
  const openIndex = source.indexOf('{', startIndex);
  expect(openIndex).toBeGreaterThanOrEqual(0);
  let depth = 0;
  for (let index = openIndex; index < source.length; index += 1) {
    const char = source[index];
    if (char === '{') depth += 1;
    if (char === '}') depth -= 1;
    if (depth === 0) return source.slice(openIndex + 1, index);
  }
  throw new Error('Unclosed CSS block');
}

function mediaBlock(source, query) {
  const startIndex = source.indexOf(`@media ${query}`);
  expect(startIndex).toBeGreaterThanOrEqual(0);
  return blockAfter(source, startIndex);
}

function selectorBlocks(source, selector) {
  const blocks = [];
  let startIndex = source.indexOf(selector);
  while (startIndex >= 0) {
    blocks.push(blockAfter(source, startIndex));
    startIndex = source.indexOf(selector, startIndex + selector.length);
  }
  expect(blocks.length).toBeGreaterThan(0);
  return blocks;
}

function expectSelectorDeclaration(source, selector, declaration) {
  expect(selectorBlocks(source, selector).some((block) => block.includes(declaration))).toBe(true);
}

describe('chat responsive CSS contract', () => {
  const css = readFileSync(join(process.cwd(), 'src/styles.css'), 'utf8');
  const tabletCss = mediaBlock(css, '(max-width: 900px)');
  const phoneCss = mediaBlock(css, '(max-width: 640px)');

  it('prevents horizontal chat overflow and keeps the mobile composer reachable', () => {
    expect(css).toContain('overflow-x: clip');
    expect(css).toContain('overflow-x: hidden');
    expect(css).toContain('overscroll-behavior: contain');
    expect(css).toContain('position: sticky');
    expect(css).toContain('env(safe-area-inset-bottom)');
  });

  it('prioritizes the chat and moves completion requirements below it on mobile', () => {
    expect(tabletCss).toContain('grid-template-columns: 1fr');
    expectSelectorDeclaration(tabletCss, '.dialogue-shell', 'grid-template-rows: minmax(58svh, auto) auto');
    expectSelectorDeclaration(tabletCss, '.chat-panel', 'order: 1');
    expectSelectorDeclaration(tabletCss, '.dialogue-sidebar', 'order: 2');
    expect(css).not.toContain('order: -1');
  });

  it('keeps questionnaire scale endpoint labels on the left and right in narrow layouts', () => {
    expectSelectorDeclaration(
      tabletCss,
      '.scale-row,\n  .semantic .scale-row',
      'grid-template-columns: minmax(4.2rem, 0.7fr) minmax(0, 1fr) minmax(4.2rem, 0.7fr)'
    );
    expectSelectorDeclaration(tabletCss, '.scale-anchor:last-child', 'text-align: end');
    expectSelectorDeclaration(tabletCss, '.scale-options', 'min-inline-size: 0');
    expectSelectorDeclaration(tabletCss, '.scale-options', 'overflow-x: auto');
    expect(
      selectorBlocks(tabletCss, '.scale-row,\n  .semantic .scale-row').some((block) =>
        block.includes('grid-template-columns: 1fr')
      )
    ).toBe(false);
  });

  it('lets the mobile dialogue page scroll while preserving a large chat viewport', () => {
    expectSelectorDeclaration(tabletCss, '.app-shell:has(.dialogue-flow)', 'block-size: auto');
    expectSelectorDeclaration(tabletCss, '.dialogue-flow,\n  .dialogue-layout,\n  .dialogue-shell', 'overflow: visible');
    expectSelectorDeclaration(phoneCss, '.app-shell:has(.dialogue-flow)', 'overflow: visible');
    expectSelectorDeclaration(phoneCss, '.dialogue-shell', 'grid-template-rows: minmax(70svh, auto) auto');
    expectSelectorDeclaration(phoneCss, '.chat-panel', 'min-block-size: clamp(540px, 76svh, 820px)');
    expectSelectorDeclaration(phoneCss, '.dialogue-progress', 'grid-template-columns: repeat(2, minmax(0, 1fr))');
  });
});
