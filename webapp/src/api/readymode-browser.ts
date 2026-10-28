import type { AgentDialerCountsResponse, DownloadRequest } from './readymode'
import type { ReadyModeStatus } from '@/types/api'
import { apiUrl } from './client'

const CHANNEL = 'vos-readymode-connector'
const CONNECTOR_TIMEOUT_MS = 2_000
const RESPONSE_TIMEOUT_MS = 90_000

interface ConnectorResponse {
  channel?: string
  type?: string
  id?: string
  result?: AgentDialerCountsResponse | ReadyModeStatus
  error?: string
}

export class BrowserConnectorUnavailableError extends Error {
  constructor() {
    super('The Chrome ReadyMode connector is not installed or needs a page reload.')
    this.name = 'BrowserConnectorUnavailableError'
  }
}

export function getAgentDialerCountsFromBrowser(request: {
  agent_name: string
  start_date: string
  end_date: string
}): Promise<AgentDialerCountsResponse> {
  return new Promise((resolve, reject) => {
    const id = crypto.randomUUID()
    let timeout = window.setTimeout(() => {
      window.removeEventListener('message', handleMessage)
      reject(new BrowserConnectorUnavailableError())
    }, CONNECTOR_TIMEOUT_MS)

    function handleMessage(event: MessageEvent<ConnectorResponse>) {
      if (event.source !== window || event.origin !== window.location.origin) return
      const response = event.data
      if (response?.channel !== CHANNEL || response.id !== id) return
      if (response.type === 'agent-counts-started') {
        window.clearTimeout(timeout)
        timeout = window.setTimeout(() => {
          window.removeEventListener('message', handleMessage)
          reject(new Error('The Chrome ReadyMode check took too long. Try again.'))
        }, RESPONSE_TIMEOUT_MS)
        return
      }
      if (response.type !== 'agent-counts-result') return

      window.clearTimeout(timeout)
      window.removeEventListener('message', handleMessage)
      if (response.error) reject(new Error(response.error))
      else if (response.result && !('status' in response.result)) resolve(response.result)
      else reject(new Error('The Chrome ReadyMode connector returned an empty response.'))
    }

    window.addEventListener('message', handleMessage)
    window.postMessage({ channel: CHANNEL, type: 'agent-counts', id, payload: request }, window.location.origin)
  })
}

export function runReadymodeAuditFromBrowser(
  request: DownloadRequest,
  token: string,
  signal?: AbortSignal,
): Promise<ReadyModeStatus> {
  return new Promise((resolve, reject) => {
    const id = crypto.randomUUID()
    const cleanup = () => {
      window.clearTimeout(timeout)
      window.removeEventListener('message', handleMessage)
      signal?.removeEventListener('abort', handleAbort)
    }
    let timeout = window.setTimeout(() => {
      cleanup()
      reject(new BrowserConnectorUnavailableError())
    }, CONNECTOR_TIMEOUT_MS)

    function handleAbort() {
      window.postMessage({ channel: CHANNEL, type: 'browser-audit-cancel', id }, window.location.origin)
      cleanup()
      reject(new DOMException('ReadyMode audit cancelled.', 'AbortError'))
    }

    function handleMessage(event: MessageEvent<ConnectorResponse>) {
      if (event.source !== window || event.origin !== window.location.origin) return
      const response = event.data
      if (response?.channel !== CHANNEL || response.id !== id) return
      if (response.type === 'browser-audit-started') {
        window.clearTimeout(timeout)
        timeout = window.setTimeout(() => {
          window.removeEventListener('message', handleMessage)
          reject(new Error('ReadyMode import is taking too long. Check your Chrome session and retry.'))
        }, 30 * 60_000)
        return
      }
      if (response.type !== 'browser-audit-result') return
      cleanup()
      if (response.error) reject(new Error(response.error))
      else if (response.result && 'status' in response.result) resolve(response.result)
      else reject(new Error('The Chrome connector returned an empty audit result.'))
    }

    window.addEventListener('message', handleMessage)
    if (signal?.aborted) {
      handleAbort()
      return
    }
    signal?.addEventListener('abort', handleAbort, { once: true })
    window.postMessage({
      channel: CHANNEL,
      type: 'browser-audit',
      id,
      payload: {
        id,
        request,
        token,
        apiUrl: new URL(apiUrl('/api/readymode/browser-import'), window.location.origin).toString(),
      },
    }, window.location.origin)
  })
}
