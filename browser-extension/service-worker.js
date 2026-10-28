importScripts('ready-mode-client.js');

const TRUSTED_PAGE_ORIGINS = new Set([
  'https://vos-tool.up.railway.app',
  'http://localhost:5173',
  'http://127.0.0.1:5173',
]);
const activeAudits = new Map();

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!['VOS_READYM_AGENT_COUNTS', 'VOS_READYM_BROWSER_AUDIT', 'VOS_CANCEL_BROWSER_AUDIT'].includes(message?.type)) return false;
  const senderOrigin = sender.url ? new URL(sender.url).origin : '';
  if (!TRUSTED_PAGE_ORIGINS.has(senderOrigin)) {
    sendResponse({ error: 'Request came from an unrecognized VOS page.' });
    return false;
  }

  if (message.type === 'VOS_CANCEL_BROWSER_AUDIT') {
    activeAudits.get(message.payload?.id)?.abort();
    sendResponse({ cancelled: true });
    return false;
  }

  let controller;
  if (message.type === 'VOS_READYM_BROWSER_AUDIT') {
    controller = new AbortController();
    activeAudits.set(message.payload.id, controller);
  }
  const operation = message.type === 'VOS_READYM_BROWSER_AUDIT'
    ? VOSReadyModeClient.runBrowserAudit(message.payload.request, { ...message.payload, signal: controller.signal })
    : VOSReadyModeClient.getAgentDialerCounts(message.payload);
  operation
    .then((result) => sendResponse({ result }))
    .catch((error) => sendResponse({ error: error instanceof Error ? error.message : 'ReadyMode check failed.' }))
    .finally(() => {
      if (message.payload?.id) activeAudits.delete(message.payload.id);
    });
  return true;
});
