const VOS_CHANNEL = 'vos-readymode-connector';

window.addEventListener('message', (event) => {
  if (event.source !== window || event.origin !== window.location.origin) return;
  const request = event.data;
  if (request?.channel === VOS_CHANNEL && request.type === 'browser-audit-cancel'
    && typeof request.id === 'string') {
    chrome.runtime.sendMessage({ type: 'VOS_CANCEL_BROWSER_AUDIT', payload: { id: request.id } });
    return;
  }
  if (request?.channel !== VOS_CHANNEL || !['agent-counts', 'browser-audit'].includes(request?.type)
    || typeof request.id !== 'string') return;

  const audit = request.type === 'browser-audit';
  const operationType = audit ? 'browser-audit' : 'agent-counts';
  const messageType = audit ? 'VOS_READYM_BROWSER_AUDIT' : 'VOS_READYM_AGENT_COUNTS';

  window.postMessage({
    channel: VOS_CHANNEL,
    type: `${operationType}-started`,
    id: request.id,
  }, window.location.origin);

  chrome.runtime.sendMessage({ type: messageType, payload: request.payload })
    .then((response) => {
      window.postMessage({
        channel: VOS_CHANNEL,
        type: `${operationType}-result`,
        id: request.id,
        ...response,
      }, window.location.origin);
    })
    .catch(() => {
      window.postMessage({
        channel: VOS_CHANNEL,
        type: `${operationType}-result`,
        id: request.id,
        error: 'VOS ReadyMode connector could not be reached. Reload this page and retry.',
      }, window.location.origin);
    });
});
