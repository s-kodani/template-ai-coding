import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';

const directory = new URL('.', import.meta.url);
const bundled = await build({
  entryPoints: [fileURLToPath(new URL('app.js', directory))],
  bundle: true, write: false, minify: true, format: 'iife', target: 'es2022', legalComments: 'eof'
});
const [template, style] = await Promise.all([
  readFile(new URL('index.html', directory), 'utf8'),
  readFile(new URL('style.css', directory), 'utf8')
]);
// Callbacks keep SDK strings such as "$&" literal during template insertion.
const html = template.replace('/* APP_STYLE */', () => style).replace(
  '/* APP_SCRIPT */', () => bundled.outputFiles[0].text.replace(/<\/script/gi, '<\\/script')
);
const output = new URL('../../src/knowledge_mcp/static/search-results.html', directory);
await mkdir(new URL('.', output), { recursive: true });
await writeFile(output, html);
console.log(fileURLToPath(output));
