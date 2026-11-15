import { App, applyDocumentTheme, applyHostStyleVariables } from '@modelcontextprotocol/ext-apps';
import { createSearchController } from './search.js';

const root = document.getElementById('knowledge-search');
const list = root.querySelector('#results');
const detail = root.querySelector('#detail');
const range = root.querySelector('#range');
const errorBox = root.querySelector('#error');
const size = root.querySelector('#page-size');
const previous = root.querySelector('#previous');
const next = root.querySelector('#next');
const app = new App({ name: 'knowledge-search', version: '0.1.0' }, {}, { autoResize: true });
const controller = createSearchController(request => app.callServerTool(request), render);

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function retry(label, callback) {
  const button = element('button', 'retry', label);
  button.type = 'button';
  button.addEventListener('click', callback);
  return button;
}
function focusResult(documentId) {
  Array.from(list.querySelectorAll('button')).find(button => button.dataset.documentId === documentId)?.focus({ preventScroll: true });
}
function render(state) {
  const focused = root.contains(document.activeElement) ? document.activeElement.getAttribute('aria-label') : null;
  root.querySelector('#query').textContent = state.query || '検索結果を待っています';
  root.setAttribute('aria-busy', String(state.loading));
  const { offset, page_size: pageSize, has_more: hasMore } = state.pagination;
  const customSize = Array.from(size.options).find(option => option.dataset.custom);
  if (customSize) customSize.remove();
  if (![5, 10, 20].includes(pageSize)) {
    const option = element('option', '', `${pageSize}件`);
    option.value = String(pageSize);
    option.dataset.custom = 'true';
    size.append(option);
  }
  size.value = String(pageSize);
  size.disabled = state.loading || !state.query;
  previous.disabled = state.loading || offset === 0;
  next.disabled = state.loading || !hasMore;
  root.querySelector('#page-label').textContent = `${Math.floor(offset / pageSize) + 1}ページ目`;
  range.textContent = state.loading ? '検索中…' : state.hits.length ? `${offset + 1}–${offset + state.hits.length}件を表示 · 類似度順` : '検索結果 0件';
  root.querySelector('#empty').hidden = state.loading || !!state.hits.length || !!state.error;
  errorBox.hidden = !state.error;
  errorBox.replaceChildren();
  if (state.error) {
    errorBox.append(element('span', '', state.error));
    if (state.retryPage) errorBox.append(retry('ページ取得を再試行', () => controller.loadPage(state.retryPage.offset, state.retryPage.pageSize)));
  }
  list.start = offset + 1;
  list.replaceChildren();
  for (const [index, hit] of state.hits.entries()) {
    const item = element('li', 'result' + (state.selected === hit.document_id ? ' is-active' : ''));
    const titleRow = element('div', 'title-row');
    const title = element('button', 'title', hit.title);
    title.type = 'button';
    title.dataset.documentId = hit.document_id;
    title.setAttribute('aria-label', `${offset + index + 1}位 ${hit.title}の本文を表示`);
    title.setAttribute('aria-pressed', String(state.selected === hit.document_id));
    title.disabled = state.loading;
    title.addEventListener('click', () => controller.selectDocument(hit.document_id));
    titleRow.append(element('span', 'rank', String(offset + index + 1).padStart(2, '0')), title);
    const meta = element('div', 'result-meta');
    const source = element('span', 'source', hit.source ? String(hit.source).split('/').pop() : '出典なし');
    if (hit.source) source.title = hit.source;
    meta.append(source, element('span', 'score', `類似度 ${Number.isFinite(hit.similarity) ? hit.similarity.toFixed(3) : '—'}`));
    item.append(titleRow, element('p', 'excerpt', hit.excerpt), meta);
    list.append(item);
  }
  detail.replaceChildren();
  if (state.selected) {
    const hit = state.hits.find(value => value.document_id === state.selected);
    const top = element('div', 'detail-top');
    const close = element('button', 'close', '×');
    close.type = 'button';
    close.setAttribute('aria-label', '本文詳細を閉じる');
    close.addEventListener('click', () => { const id = state.selected; controller.closeDetail(); focusResult(id); });
    top.append(element('span', '', '本文詳細 · 検索対象チャンク'), close);
    detail.append(top, element('h2', '', state.detail?.title || hit?.title || '本文'));
    const source = state.detail?.source || hit?.source;
    if (source) detail.append(element('div', 'detail-path', source));
    if (state.detailLoading) detail.append(element('p', 'detail-empty', '本文を取得中…'));
    else if (state.detailError) {
      const message = element('div', 'error', state.detailError);
      message.setAttribute('role', 'alert');
      message.append(retry('本文取得を再試行', () => controller.selectDocument(state.selected)));
      detail.append(message);
    } else if (state.detail) detail.append(element('div', 'detail-body', state.detail.content));
  } else detail.append(element('p', 'detail-empty', '文書を選ぶと本文を表示します'));
  if (focused) Array.from(root.querySelectorAll('button[aria-label]')).find(button => button.getAttribute('aria-label') === focused)?.focus({ preventScroll: true });
}
function applyContext(context) {
  if (context?.theme) applyDocumentTheme(context.theme);
  if (context?.styles?.variables) applyHostStyleVariables(context.styles.variables);
}
previous.addEventListener('click', () => controller.loadPage(Math.max(0, controller.state.pagination.offset - controller.state.pagination.page_size)));
next.addEventListener('click', () => controller.loadPage(controller.state.pagination.next_offset));
size.addEventListener('change', () => controller.loadPage(0, Number(size.value)));
app.addEventListener('toolinput', params => controller.acceptInput(params.arguments));
app.addEventListener('toolresult', result => controller.acceptResult(result));
app.addEventListener('toolcancelled', () => controller.acceptResult({ isError: true, content: [{ type: 'text', text: '検索がキャンセルされました。' }] }));
app.addEventListener('hostcontextchanged', applyContext);
render(controller.state);
app.connect().then(() => applyContext(app.getHostContext())).catch(() => {
  controller.acceptResult({ isError: true, content: [{ type: 'text', text: 'Hostに接続できませんでした。接続を確認してください。' }] });
});
