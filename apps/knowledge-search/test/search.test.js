import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createSearchController } from '../search.js';

const hit = id => ({ document_id: id, title: `Title ${id}`, excerpt: 'excerpt', source: null, similarity: .9 });
const page = (offset = 0, ids = ['a', 'b'], hasMore = true, pageSize = 5) => ({
  structuredContent: { query: 'tracing', hits: ids.map(hit), pagination: { offset, page_size: pageSize, has_more: hasMore, next_offset: hasMore ? offset + pageSize : null } }
});
const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b; }); return { promise, resolve, reject }; };

test('next page uses server offset, preserves the query, and clears details', async () => {
  const calls = [];
  const search = createSearchController(async request => { calls.push(request); return page(5, ['f', 'g'], false); });
  search.acceptResult(page());
  await search.loadPage(5);
  assert.deepEqual(calls, [{ name: 'search_knowledge', arguments: { query: 'tracing', top_k: 5, offset: 5 } }]);
  assert.deepEqual(search.state.hits.map(value => value.document_id), ['f', 'g']);
  assert.equal(search.state.pagination.has_more, false);
  assert.equal(search.state.selected, null);
});

test('page failure keeps the displayed page and surfaces an error', async () => {
  const search = createSearchController(async () => { throw new Error('offline'); });
  search.acceptResult(page());
  await search.loadPage(5);
  assert.equal(search.state.pagination.offset, 0);
  assert.equal(search.state.hits[0].document_id, 'a');
  assert.equal(search.state.error, 'offline');
  assert.equal(search.state.loading, false);
});

test('page size change requests the first server page', async () => {
  let request;
  const search = createSearchController(async value => { request = value; return page(0, ['a'], false, 20); });
  search.acceptResult(page(10));
  await search.loadPage(0, 20);
  assert.deepEqual(request.arguments, { query: 'tracing', top_k: 20, offset: 0 });
  assert.equal(search.state.pagination.page_size, 20);
});

test('a late page response cannot replace newer results', async () => {
  const first = deferred();
  const second = deferred();
  let requests = 0;
  const search = createSearchController(() => (++requests === 1 ? first.promise : second.promise));
  search.acceptResult(page());
  const oldRequest = search.loadPage(5);
  const newRequest = search.loadPage(10);
  second.resolve(page(10, ['new']));
  await newRequest;
  first.resolve(page(5, ['old']));
  await oldRequest;
  assert.equal(search.state.hits[0].document_id, 'new');
  assert.equal(search.state.pagination.offset, 10);
});

test('selecting a new chunk ignores the previous detail response', async () => {
  const first = deferred();
  const second = deferred();
  const search = createSearchController(request => request.arguments.document_id === 'a' ? first.promise : second.promise);
  search.acceptResult(page());
  const oldRequest = search.selectDocument('a');
  const newRequest = search.selectDocument('b');
  second.resolve({ structuredContent: { document_id: 'b', title: 'B', content: '<script>body</script>' } });
  await newRequest;
  first.resolve({ structuredContent: { document_id: 'a', title: 'A', content: 'old' } });
  await oldRequest;
  assert.equal(search.state.selected, 'b');
  assert.equal(search.state.detail.content, '<script>body</script>');
});

test('structured errors and missing documents have a visible failure state', async () => {
  const search = createSearchController(async () => ({ structuredContent: { error: 'Document not found' } }));
  search.acceptResult(page());
  await search.selectDocument('a');
  assert.equal(search.state.detailError, 'Document not found');
  assert.equal(search.state.detailLoading, false);
  assert.equal(search.state.detail, null);
});

test('empty results do not claim a next page', () => {
  const search = createSearchController(async () => {});
  search.acceptResult(page(0, [], false));
  assert.equal(search.state.hits.length, 0);
  assert.equal(search.state.pagination.has_more, false);
});

test('legacy text JSON can initialize the app without rendering server HTML', () => {
  const search = createSearchController(async () => {});
  search.acceptResult({ content: [{ type: 'text', text: JSON.stringify(page().structuredContent) }] });
  assert.equal(search.state.query, 'tracing');
  assert.equal(search.state.hits[0].document_id, 'a');
});

test('a new model result invalidates pending app requests', async () => {
  const pending = deferred();
  const search = createSearchController(() => pending.promise);
  search.acceptResult(page());
  const request = search.loadPage(5);
  search.acceptResult(page(0, ['updated'], false));
  pending.resolve(page(5, ['stale'], false));
  await request;
  assert.equal(search.state.hits[0].document_id, 'updated');
});

test('closing detail cancels a pending result', async () => {
  const pending = deferred();
  const search = createSearchController(() => pending.promise);
  search.acceptResult(page());
  const request = search.selectDocument('a');
  search.closeDetail();
  pending.resolve({ structuredContent: { document_id: 'a', content: 'late' } });
  await request;
  assert.equal(search.state.detail, null);
  assert.equal(search.state.selected, null);
});

test('retry repeats the failed target page rather than refreshing the old page', async () => {
  const search = createSearchController(async () => { throw new Error('offline'); });
  search.acceptResult(page());
  await search.loadPage(5, 10);
  assert.deepEqual(search.state.retryPage, { offset: 5, pageSize: 10 });
});
