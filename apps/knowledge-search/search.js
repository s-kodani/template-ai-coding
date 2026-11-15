function payload(result) {
  if (result?.isError) throw new Error(result.content?.find(item => item.type === 'text')?.text || 'ツールの実行に失敗しました。');
  let value = result?.structuredContent;
  if (!value) {
    const text = result?.content?.find(item => item.type === 'text')?.text;
    if (text) value = JSON.parse(text);
  }
  if (!value || typeof value !== 'object') throw new Error('結果の形式が正しくありません。');
  if (value.error) throw new Error(String(value.error));
  return value;
}

function searchPage(result) {
  const value = payload(result);
  const p = value.pagination;
  if (typeof value.query !== 'string' || !Array.isArray(value.hits) || !p ||
      !Number.isInteger(p.offset) || p.offset < 0 || !Number.isInteger(p.page_size) ||
      p.page_size < 1 || p.page_size > 20 || typeof p.has_more !== 'boolean' ||
      (p.has_more && (!Number.isInteger(p.next_offset) || p.next_offset <= p.offset))) {
    throw new Error('検索結果の形式が正しくありません。');
  }
  return value;
}

export function createSearchController(callServerTool, onChange = () => {}) {
  const state = {
    query: '', hits: [], pagination: { offset: 0, page_size: 5, has_more: false, next_offset: null },
    selected: null, detail: null, loading: true, detailLoading: false, error: null, detailError: null,
    retryPage: null
  };
  let searchVersion = 0;
  let detailVersion = 0;
  const notify = () => onChange(state);
  function closeDetail() {
    detailVersion++;
    Object.assign(state, { selected: null, detail: null, detailLoading: false, detailError: null });
    notify();
  }
  function applyPage(value) {
    detailVersion++;
    Object.assign(state, {
      query: value.query, hits: value.hits, pagination: value.pagination, loading: false, error: null,
      selected: null, detail: null, detailLoading: false, detailError: null, retryPage: null
    });
  }
  function acceptResult(result) {
    searchVersion++;
    try { applyPage(searchPage(result)); }
    catch (error) { state.error = error.message; state.loading = false; }
    notify();
  }
  function acceptInput(input) {
    if (typeof input?.query === 'string') state.query = input.query;
    notify();
  }
  async function loadPage(offset, pageSize = state.pagination.page_size) {
    const request = ++searchVersion;
    detailVersion++;
    Object.assign(state, { loading: true, error: null, detailLoading: false });
    notify();
    try {
      const result = await callServerTool({ name: 'search_knowledge', arguments: { query: state.query, top_k: pageSize, offset } });
      if (request !== searchVersion) return;
      applyPage(searchPage(result));
    } catch (error) {
      if (request !== searchVersion) return;
      state.error = error.message || 'ページを取得できませんでした。';
      state.retryPage = { offset, pageSize };
    } finally {
      if (request === searchVersion) { state.loading = false; notify(); }
    }
  }
  async function selectDocument(documentId) {
    if (!state.hits.some(hit => hit.document_id === documentId)) return;
    const request = ++detailVersion;
    Object.assign(state, { selected: documentId, detail: null, detailLoading: true, detailError: null });
    notify();
    try {
      const result = payload(await callServerTool({ name: 'get_document', arguments: { document_id: documentId } }));
      if (request !== detailVersion) return;
      if (result.document_id !== documentId || typeof result.content !== 'string') throw new Error('本文の形式が正しくありません。');
      state.detail = result;
    } catch (error) {
      if (request !== detailVersion) return;
      state.detailError = error.message || '本文を取得できませんでした。';
    } finally {
      if (request === detailVersion) { state.detailLoading = false; notify(); }
    }
  }
  return { state, acceptInput, acceptResult, loadPage, selectDocument, closeDetail };
}
