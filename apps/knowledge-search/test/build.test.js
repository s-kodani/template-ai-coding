import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { Script } from 'node:vm';

test('bundled HTML contains one document and a valid self-contained script', () => {
  const directory = new URL('../', import.meta.url);
  execFileSync(process.execPath, ['build.mjs'], { cwd: fileURLToPath(directory) });
  const html = readFileSync(new URL('../../src/knowledge_mcp/static/search-results.html', directory), 'utf8');
  assert.equal((html.match(/<!doctype html>/g) || []).length, 1);
  assert.equal(html.includes('/* APP_SCRIPT */'), false);
  const script = html.match(/<script type="module">([\s\S]*)<\/script>/)[1];
  assert.doesNotThrow(() => new Script(script));
  assert.ok(Buffer.byteLength(html) < 5_000_000, 'Open WebUI limits UI resources to 5 MB');
});
