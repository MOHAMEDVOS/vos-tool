import { authHeaders } from '@/api/client'

export interface ReadSSEStreamOptions {
  /** JSON-serializable request body (always sent as POST). */
  body?: unknown
  /** Abort signal for cancellable streams. */
  signal?: AbortSignal
  /** When true, a non-2xx response throws (message taken from the response body,
   *  falling back to its status text) before any stream reading starts. Defaults
   *  to false: a non-ok response is read like any other — matches call sites that
   *  never checked `res.ok`. */
  checkOk?: boolean
  /** Called once per successfully-parsed SSE event — every `data:` line whose
   *  payload parses as `{ event, data }`. May throw to abort the stream; the
   *  thrown value is passed to `onParseError`. */
  onEvent: (event: string, data: unknown) => void
  /** Called when a `data:` line's envelope fails to parse, or when `onEvent`
   *  itself throws. Defaults to silently ignoring the error — every current
   *  caller treats a malformed line or keep-alive ping this way. Re-throw from
   *  inside to abort the stream and reject the returned promise. */
  onParseError?: (error: unknown) => void
}

/**
 * POSTs to `url` and reads the response body as a `text/event-stream`, dispatching
 * one `onEvent(event, data)` call per `data:` line that parses as `{ event, data }`.
 * The bearer token is attached automatically via `authHeaders()`.
 */
export async function readSSEStream(url: string, options: ReadSSEStreamOptions): Promise<void> {
  const { body, signal, checkOk = false, onEvent, onParseError } = options

  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: body !== undefined ? JSON.stringify(body) : undefined,
    signal,
  })

  if (checkOk && !res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new Error(text || `HTTP ${res.status}`)
  }

  const reader = res.body?.getReader()
  if (!reader) return

  const decoder = new TextDecoder()
  let buf = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buf += decoder.decode(value, { stream: true })
    const lines = buf.split('\n')
    buf = lines.pop() ?? ''
    for (const line of lines) {
      if (!line.startsWith('data:')) continue
      const raw = line.slice(5).trim()
      if (!raw) continue
      try {
        const { event, data } = JSON.parse(raw)
        onEvent(event, data)
      } catch (e) {
        onParseError?.(e)
      }
    }
  }
}
