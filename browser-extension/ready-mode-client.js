(function exposeReadyModeClient(root) {
  const DIALERS = [
    ['resva', 'https://resva.readymode.com/'],
    ['resva2', 'https://resva2.readymode.com/'],
    ['resva3', 'https://resva3.readymode.com/'],
    ['resva4', 'https://resva4.readymode.com/'],
    ['resva5', 'https://resva5.readymode.com/'],
    ['resva6', 'https://resva6.readymode.com/'],
    ['resva7', 'https://resva7.readymode.com/'],
  ].map(([name, url]) => ({ name, url }));
  const BASE_TYPE = '6';
  const REPORT_PATH = '/CCS%20Reports/call_log/update';

  function isBlockedDisposition(label) {
    return /voicemail|\bvm\b/i.test(String(label || ''));
  }

  function parseDispositionIds(html) {
    const select = String(html || '').match(
      /<select\b[^>]*\bname=["']report\[types\]\[\]["'][^>]*>([\s\S]*?)<\/select>/i,
    );
    if (!select) return [];

    const ids = [];
    const optionPattern = /<option\b[^>]*\bvalue=["']([^"']*)["'][^>]*>([^<]*)<\/option>/gi;
    for (const match of select[1].matchAll(optionPattern)) {
      const label = match[2].replace(/&nbsp;/gi, ' ').trim();
      if (label && match[1] !== BASE_TYPE && !isBlockedDisposition(label) && !ids.includes(match[1])) {
        ids.push(match[1]);
      }
    }
    return ids;
  }

  function parseDispositionMap(html) {
    const select = String(html || '').match(
      /<select\b[^>]*\bname=["']report\[types\]\[\]["'][^>]*>([\s\S]*?)<\/select>/i,
    );
    if (!select) return {};
    const mapping = {};
    const optionPattern = /<option\b[^>]*\bvalue=["']([^"']*)["'][^>]*>([^<]*)<\/option>/gi;
    for (const match of select[1].matchAll(optionPattern)) {
      const label = match[2].replace(/&nbsp;/gi, ' ').trim();
      if (label) mapping[label.toLowerCase()] = match[1];
    }
    return mapping;
  }

  function nameMatches(label, target) {
    const normalizedLabel = String(label || '').trim().toLowerCase();
    const normalizedTarget = String(target || '').trim().toLowerCase();
    return Boolean(normalizedTarget)
      && (normalizedLabel === normalizedTarget || normalizedLabel.startsWith(`${normalizedTarget}.`));
  }

  function resolveAgentId(userlist, target) {
    const entries = Object.entries(userlist || {}).map(([key, value]) => ({
      id: String(key).replace(/^x/i, ''),
      label: String(value).split('|').at(-1).trim(),
    }));
    return entries.find((agent) => agent.label.toLowerCase() === target.trim().toLowerCase())
      || entries.find((agent) => nameMatches(agent.label, target))
      || null;
  }

  function reportUrl(origin, request, types, agentId = '0', page = 0, campaignId = '0') {
    const url = new URL(REPORT_PATH, origin);
    const params = url.searchParams;
    params.append('update', '1');
    params.append('report[types][]', BASE_TYPE);
    for (const type of types) params.append('report[types][]', type);
    params.append('report[time_from_d]', `${formatDate(request.start_date)}${request.start_time ? ` ${request.start_time}` : ''}`);
    params.append('report[time_from_dateonly]', request.start_time ? '0' : '1');
    params.append('report[time_to_d]', formatDate(request.end_date));
    params.append('report[time_to_dateonly]', '1');
    params.append('report[restrict_uid]', agentId);
    params.append('report[restrict_campaign]', campaignId);
    params.append('report[restrict_batch]', '0');
    params.append('report[sourceFilter]', '-1');
    params.append('report[durationFilter]', '-1');
    params.append('report[callTypeFilter]', '_');
    params.append('report[page]', String(page));
    return url.toString();
  }

  function formatDate(value) {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(String(value || ''))) {
      throw new Error('Enter a valid start and end date.');
    }
    const [year, month, day] = value.split('-');
    return `${month}/${day}/${year}`;
  }

  async function responseText(response, dialer) {
    const text = await response.text();
    if (text.includes('Just a moment') || text.includes('challenge-platform')) {
      throw new Error(`${dialer.name}: ReadyMode showed a security check. Sign in to this dialer in Chrome and retry.`);
    }
    if (!response.ok) {
      throw new Error(`${dialer.name}: ReadyMode returned HTTP ${response.status}.`);
    }
    return text;
  }

  async function requestReport(fetcher, dialer, request, types, agentId = '0', page = 0, campaignId = '0') {
    const response = await fetcher(reportUrl(new URL(dialer.url).origin, request, types, agentId, page, campaignId), {
      credentials: 'include',
      headers: {
        Accept: 'application/json, text/javascript, */*; q=0.01',
        'X-Requested-With': 'XMLHttpRequest',
      },
    });
    const text = await responseText(response, dialer);
    try {
      return JSON.parse(text);
    } catch {
      throw new Error(`${dialer.name}: ReadyMode did not return call report data. Sign in again in Chrome.`);
    }
  }

  async function countAgentForDialer(fetcher, dialer, request) {
    const origin = new URL(dialer.url).origin;
    const initialResponse = await fetcher(`${origin}/CCS%20Reports/call_log`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    });
    const initialHtml = await responseText(initialResponse, dialer);
    const types = parseDispositionIds(initialHtml);
    if (!types.length) {
      throw new Error(`${dialer.name}: Could not read this dialer's call types. Sign in again in Chrome.`);
    }

    const probe = await requestReport(fetcher, dialer, request, types);
    const agent = resolveAgentId(probe.userlist, request.agent_name);
    if (!agent) return { dialer: dialer.name, url: dialer.url, found: false, count: 0 };

    const firstPage = await requestReport(fetcher, dialer, request, types, agent.id);
    const totalPages = Number.parseInt(firstPage.pages, 10) || 0;
    const firstPageCount = Object.keys(firstPage.results || {}).length;
    let count = firstPageCount;

    if (totalPages > 1) {
      const lastPage = await requestReport(fetcher, dialer, request, types, agent.id, totalPages - 1);
      count = (totalPages - 1) * 25 + Object.keys(lastPage.results || {}).length;
    }

    return { dialer: dialer.name, url: dialer.url, found: true, count };
  }

  function matchesCampaign(campaigns, target) {
    const entries = Object.entries(campaigns || {}).map(([id, label]) => ({
      id: String(id), label: String(label).trim(),
    }));
    const wanted = String(target || '').trim().toLowerCase();
    return entries.find((entry) => entry.label.toLowerCase() === wanted)
      || entries.find((entry) => entry.label.toLowerCase().startsWith(`${wanted}.`))
      || null;
  }

  function dispositionTypes(mapping, selected) {
    const entries = Object.entries(mapping || {});
    const types = [];
    const blocked = (label) => /voicemail|\bvm\b/i.test(label);
    const chosen = selected?.length
      ? selected.map((name) => entries.find(([label]) => label === name.trim().toLowerCase())
        || entries.find(([label]) => !blocked(label) && (label.includes(name.trim().toLowerCase())
          || name.trim().toLowerCase().includes(label))))
      : entries;
    for (const entry of chosen) {
      if (entry && !blocked(entry[0]) && !blocked(entry[1]) && !types.includes(String(entry[1]))) {
        types.push(String(entry[1]));
      }
    }
    return types;
  }

  function safeFilename(value) {
    return String(value || 'recording.mp3').replace(/[<>:"/\\|?*\x00-\x1f]/g, '_').slice(0, 180);
  }

  async function getAuditRecordsForDialer(fetcher, dialer, request) {
    const origin = new URL(dialer.url).origin;
    const initial = await fetcher(`${origin}/CCS%20Reports/call_log`, {
      method: 'POST', credentials: 'include', headers: { 'X-Requested-With': 'XMLHttpRequest' },
    });
    const mapping = parseDispositionMap(await responseText(initial, dialer));
    if (!Object.keys(mapping).length) throw new Error(`${dialer.name}: Could not read call types. Sign in to this dialer in Chrome.`);

    const types = dispositionTypes(mapping, request.dispositions);
    const probe = await requestReport(fetcher, dialer, request, types);
    let agentId = '0';
    let campaignId = '0';
    if (request.campaign_name?.trim()) {
      const campaign = matchesCampaign(probe.campaignlist, request.campaign_name);
      if (!campaign) throw new Error(`${dialer.name}: Campaign not found.`);
      campaignId = campaign.id;
    } else if (request.agent_name?.trim() && !['all users', 'all agents', 'any'].includes(request.agent_name.trim().toLowerCase())) {
      const agent = resolveAgentId(probe.userlist, request.agent_name);
      if (!agent) throw new Error(`${dialer.name}: Agent not found.`);
      agentId = agent.id;
    }

    const maxCalls = Math.max(1, Number(request.max_calls) || 50);
    const firstPage = await requestReport(fetcher, dialer, request, types, agentId, 0, campaignId);
    const totalPages = Math.min(2000, Number.parseInt(firstPage.pages, 10) || 0);
    const records = [];
    const seenRecordingIds = new Set();
    for (let page = 0; page < totalPages && records.length < maxCalls; page += 1) {
      const report = page === 0
        ? firstPage
        : await requestReport(fetcher, dialer, request, types, agentId, page, campaignId);
      for (const row of Object.values(report.results || {})) {
        if (records.length >= maxCalls) break;
        const rec = String(row.RecId || '').trim();
        const type = String(row.Type || '').trim();
        if (!rec || isBlockedDisposition(type) || seenRecordingIds.has(rec)) continue;
        seenRecordingIds.add(rec);
        const fileText = String(row.File || '');
        const phone = fileText.match(/\(?\d{3}\)?[-\s]?\d{3}[-\s]?\d{4}/)?.[0] || 'unknown';
        const filename = safeFilename(`${row.User || 'Unknown_Agent'} _ ${row.Time || 'Unknown_Time'} _ ${phone} _ ${type || 'Unknown_Type'}.mp3`);
        const recordingUrl = new URL(rec, origin);
        if (recordingUrl.origin !== origin) continue;
        recordingUrl.searchParams.set('force_dl', '1');
        records.push({
          dialer: dialer.name,
          dialer_host: new URL(dialer.url).host,
          recording_id: rec.split('?')[0],
          filename,
          type,
          url: recordingUrl.toString(),
        });
      }
    }
    return records;
  }

  async function runBrowserAudit(request, { token, apiUrl, signal }, fetcher = fetch) {
    if (!token || typeof token !== 'string') throw new Error('VOS sign-in is required.');
    const api = new URL(apiUrl, globalThis.location?.origin || 'https://vos-tool.up.railway.app');
    if (![
      'https://vos-tool.up.railway.app',
      'http://localhost:5173', 'http://127.0.0.1:5173',
      'http://localhost:8000', 'http://127.0.0.1:8000',
    ].includes(api.origin)) {
      throw new Error('VOS API address is not trusted by the connector.');
    }
    const selectedDialers = DIALERS.filter((dialer) => [request.dialer_url, request.dialer_url_2]
      .some((value) => value && new URL(value).host === new URL(dialer.url).host));
    if (!selectedDialers.length) throw new Error('Choose a supported ReadyMode dialer.');
    const controlledFetch = (url, options = {}) => fetcher(url, { ...options, signal });

    const records = [];
    const failures = [];
    for (const dialer of selectedDialers) {
      try {
        records.push(...await getAuditRecordsForDialer(controlledFetch, dialer, request));
      } catch (error) {
        failures.push(error instanceof Error ? error.message : `${dialer.name}: report request failed.`);
        if (dialer === selectedDialers[0]) throw error;
      }
    }
    if (!records.length) throw new Error(failures.join(' ') || 'No call recordings matched these filters.');

    const form = new FormData();
    form.append('audit_request', JSON.stringify(request));
    const manifest = [];
    let totalBytes = 0;
    for (const record of records) {
      const response = await controlledFetch(record.url, { credentials: 'include' });
      const blob = await response.blob();
      if (!response.ok || blob.type.includes('html') || !blob.size) {
        throw new Error(`${record.dialer}: could not download ${record.filename}; check the Chrome session.`);
      }
      totalBytes += blob.size;
      if (totalBytes > 90 * 1024 * 1024) throw new Error('These recordings are too large to import in one audit. Reduce the call limit.');
      manifest.push({
        dialer_host: record.dialer_host,
        recording_id: record.recording_id,
        filename: record.filename,
        type: record.type,
      });
      form.append('files', blob, record.filename);
    }
    form.append('manifest', JSON.stringify(manifest));
    const response = await controlledFetch(api.toString(), {
      method: 'POST', headers: { Authorization: `Bearer ${token}` }, body: form,
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      throw new Error(body.detail || `VOS could not import recordings (HTTP ${response.status}).`);
    }
    return response.json();
  }

  async function getAgentDialerCounts(request, fetcher = fetch) {
    if (!request.agent_name?.trim()) throw new Error('Agent name is required.');
    formatDate(request.start_date);
    formatDate(request.end_date);

    const settled = await Promise.all(DIALERS.map(async (dialer) => {
      try {
        return { result: await countAgentForDialer(fetcher, dialer, request) };
      } catch (error) {
        const message = error instanceof Error ? error.message : 'ReadyMode request failed.';
        return { error: message };
      }
    }));
    const results = settled.flatMap((item) => item.result ? [item.result] : []);
    const failed = settled.flatMap((item) => item.error ? [item.error] : []);
    const found = results.filter((result) => result.found);
    const busiest = found.length
      ? found.reduce((best, result) => result.count > best.count ? result : best)
      : null;

    return { agent_name: request.agent_name.trim(), results, busiest, failed };
  }

  const client = { DIALERS, parseDispositionIds, parseDispositionMap, resolveAgentId, reportUrl, getAgentDialerCounts, runBrowserAudit };
  root.VOSReadyModeClient = client;
  if (typeof module !== 'undefined' && module.exports) module.exports = client;
})(globalThis);
