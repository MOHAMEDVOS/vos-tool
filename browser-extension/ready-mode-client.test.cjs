const test = require('node:test');
const assert = require('node:assert/strict');
const { parseDispositionIds, parseDispositionMap, resolveAgentId, getAgentDialerCounts, runBrowserAudit } = require('./ready-mode-client.js');

function response(body, status = 200, contentType = 'text/html') {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: () => contentType },
    text: async () => body,
  };
}

test('parses dialer-specific types and excludes voicemail', () => {
  const html = `<select name='report[types][]'>
    <option value='6'>All</option><option value='20'>Callback</option>
    <option value='21'>Voicemail</option><option value='22'>VM - No Answer</option>
  </select>`;
  assert.deepEqual(parseDispositionIds(html), ['20']);
});

test('parses the selected dialer disposition labels and ids', () => {
  const html = `<select name='report[types][]'><option value='6'>All</option><option value='20'>Callback</option><option value='21'>Voicemail</option></select>`;
  assert.deepEqual(parseDispositionMap(html), { all: '6', callback: '20', voicemail: '21' });
});

test('matches agent names exactly before the dot-suffix fallback', () => {
  assert.deepEqual(resolveAgentId({ x10: 'Agents|Nora Smith.Team A', x11: 'Agents|Nora Smith' }, 'Nora Smith'), {
    id: '11', label: 'Nora Smith',
  });
  assert.deepEqual(resolveAgentId({ x10: 'Agents|Nora Smith.Team A' }, 'Nora Smith'), {
    id: '10', label: 'Nora Smith.Team A',
  });
  assert.equal(resolveAgentId({ x10: 'Agents|Other' }, 'Missing'), null);
});

test('counts paginated agent calls and reports unavailable dialer sessions', async () => {
  const calls = [];
  const fetcher = async (url, options = {}) => {
    const parsed = new URL(url);
    calls.push({ url: parsed, options });
    if (parsed.pathname.endsWith('/call_log')) return response(`<select name="report[types][]"><option value="20">Callback</option><option value="21">Voicemail</option></select>`);
    if (parsed.hostname === 'resva.readymode.com') return response('<title>Just a moment...</title>', 403);
    const agentId = parsed.searchParams.get('report[restrict_uid]');
    const page = Number(parsed.searchParams.get('report[page]'));
    if (agentId === '0') return response(JSON.stringify({ userlist: { x42: 'Agents|Nora Smith' } }), 200, 'application/json');
    return response(JSON.stringify({
      pages: '3',
      results: Object.fromEntries(Array.from({ length: page === 2 ? 5 : 25 }, (_, index) => [String(index), {}])),
    }), 200, 'application/json');
  };

  const result = await getAgentDialerCounts({
    agent_name: 'Nora Smith', start_date: '2026-10-01', end_date: '2026-10-28',
  }, fetcher);

  assert.equal(result.busiest.count, 55);
  assert.equal(result.results.length, 6);
  assert.equal(result.failed.length, 1);
  assert.match(result.failed[0], /security check/i);
  assert.ok(calls.every(({ options }) => options.credentials === 'include'));
  assert.ok(calls.every(({ url }) => url.hostname.endsWith('.readymode.com')));
  assert.ok(calls.filter(({ url }) => url.pathname.includes('/update'))
    .every(({ url }) => !url.searchParams.getAll('report[types][]').includes('21')));
});

test('downloads recordings through the signed-in dialer and posts them to VOS', async () => {
  const calls = [];
  const fetcher = async (url, options = {}) => {
    const parsed = new URL(url);
    calls.push({ url: parsed, options });
    if (parsed.hostname === 'resva.readymode.com' && parsed.pathname.endsWith('/call_log')) {
      return response(`<select name='report[types][]'><option value='20'>Callback</option><option value='21'>Voicemail</option></select>`);
    }
    if (parsed.hostname === 'resva.readymode.com' && parsed.pathname.endsWith('/update')) {
      if (!parsed.searchParams.has('report[restrict_uid]') || parsed.searchParams.get('report[restrict_uid]') === '0') {
        return response(JSON.stringify({
          userlist: { x42: 'Agents|Nora Smith' },
          pages: '1',
          results: {
            0: { RecId: '/recordings/r1.mp3', User: 'Nora Smith', Time: '10:00', Type: 'Callback', File: '(555) 111-2222' },
            1: { RecId: '/recordings/vm.mp3', User: 'Nora Smith', Time: '10:01', Type: 'Voicemail', File: '(555) 111-2222' },
          },
        }));
      }
      return response(JSON.stringify({
        pages: '1',
        results: {
          0: { RecId: '/recordings/r1.mp3', User: 'Nora Smith', Time: '10:00', Type: 'Callback', File: '(555) 111-2222' },
          1: { RecId: '/recordings/vm.mp3', User: 'Nora Smith', Time: '10:01', Type: 'Voicemail', File: '(555) 111-2222' },
        },
      }));
    }
    if (parsed.hostname === 'resva.readymode.com' && parsed.pathname.endsWith('/recordings/r1.mp3')) {
      return { ok: true, status: 200, blob: async () => new Blob(['audio bytes'], { type: 'audio/mpeg' }) };
    }
    if (parsed.hostname === 'vos-tool.up.railway.app' && parsed.pathname === '/api/readymode/browser-import') {
      assert.equal(options.method, 'POST');
      assert.equal(options.headers.Authorization, 'Bearer vos-token');
      assert.equal(options.body.getAll('files').length, 1);
      assert.equal(JSON.parse(options.body.get('manifest'))[0].recording_id, '/recordings/r1.mp3');
      return { ok: true, status: 200, json: async () => ({ status: 'completed', downloaded_count: 1 }) };
    }
    throw new Error(`Unexpected request: ${url}`);
  };

  const result = await runBrowserAudit({
    dialer_url: 'https://resva.readymode.com/',
    agent_name: 'Nora Smith',
    max_calls: 5,
    start_date: '2026-10-01',
    end_date: '2026-10-28',
    dispositions: [],
  }, {
    token: 'vos-token',
    apiUrl: 'https://vos-tool.up.railway.app/api/readymode/browser-import',
  }, fetcher);

  assert.equal(result.downloaded_count, 1);
  assert.ok(calls.some(({ url }) => url.pathname.endsWith('/recordings/r1.mp3')));
  assert.ok(calls.filter(({ url }) => url.pathname.endsWith('/update'))
    .every(({ url }) => url.searchParams.getAll('report[types][]').filter((id) => id === '6').length === 1));
  assert.ok(calls.every(({ url }) => url.hostname === 'resva.readymode.com'
    || url.hostname === 'vos-tool.up.railway.app'));
});
