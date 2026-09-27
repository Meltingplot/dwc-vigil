'use strict'

/**
 * Talking to the Vigil daemon.
 *
 * The daemon registers its HTTP endpoints with DSF (`cmd.add_http_endpoint`), which
 * serves them under `/machine/<pluginId>/…` on the very origin DWC itself is served
 * from. That is identical on DSF 3.6 and 3.7, which is why every call in here is a
 * plain `fetch` and this module is shared verbatim by both UI shells.
 *
 * The one thing DWC contributes is the session key: DSF passes plugin endpoints every
 * request, logged in or not, and the daemon answers 401 unless the request carries the
 * `X-Session-Key` of a live session. Every call therefore takes the host adapter and
 * sends the key DWC's connector logged in with.
 */

/** Base path DSF serves this plugin's HTTP endpoints under. */
export const API_BASE = '/machine/Vigil'

/** How long to wait for the daemon to register its endpoints after a start. */
export const BACKEND_WAIT_ATTEMPTS = 15

/** Delay between endpoint probes while waiting for the daemon. */
export const BACKEND_WAIT_INTERVAL = 1000

/**
 * The session key held by a DWC connector, or `null`.
 *
 * `RestConnector` (SBC mode) logs in with `/machine/connect` before anything else, also
 * when no password is set, and replaces the key on every reconnect. The field is
 * `private` in the connector's typings, but it is a plain property at runtime and
 * neither DWC store offers a public accessor. The public alternative, the store's
 * `request()`, turns every 4xx other than 401/403/404 into "bad status code N" and
 * would lose the daemon's validation messages. `PollConnector` (standalone) has no key.
 *
 * [both] Checked in @duet3d/connectors 3.6.0 (DWC v3.6-dev) and 3.7.0-rc.2
 * (DWC v3.7-dev), 2026-09-27.
 *
 * @param {object|null|undefined} connector
 * @returns {string|null}
 */
export function connectorSessionKey(connector) {
    const key = connector && connector.sessionKey
    return typeof key === 'string' && key !== '' ? key : null
}

/**
 * Headers that authenticate a request with DSF.
 *
 * @param {HostAdapter} host
 * @returns {Record<string, string>}
 */
function authHeaders(host) {
    const key = host.sessionKey()
    return key ? { 'X-Session-Key': key } : {}
}

/**
 * Turn a failed response into an Error carrying the daemon's own message.
 *
 * The handlers answer errors as `{"error": "..."}` with a 4xx/5xx status; a 404 from
 * DSF itself (backend not running) has no body at all, hence the fallbacks.
 *
 * @param {Response} resp
 * @returns {Promise<Error>}
 */
async function toError(resp) {
    const body = await resp.json().catch(() => ({}))
    return new Error(body.error || resp.statusText || 'Request failed')
}

/**
 * GET a JSON endpoint.
 *
 * @param {HostAdapter} host Supplies the session key
 * @param {string} endpoint Path below {@link API_BASE}, e.g. `history?days=30`
 * @returns {Promise<object>} Parsed response body
 */
export async function apiGet(host, endpoint) {
    const resp = await fetch(`${API_BASE}/${endpoint}`, { headers: authHeaders(host) })
    if (!resp.ok) {
        throw await toError(resp)
    }
    return resp.json()
}

/**
 * POST JSON to an endpoint.
 *
 * @param {HostAdapter} host Supplies the session key
 * @param {string} endpoint Path below {@link API_BASE}
 * @param {object} [data] Request body
 * @returns {Promise<object>} Parsed response body
 */
export async function apiPost(host, endpoint, data = {}) {
    const resp = await fetch(`${API_BASE}/${endpoint}`, {
        method: 'POST',
        headers: { ...authHeaders(host), 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
    })
    if (!resp.ok) {
        throw await toError(resp)
    }
    return resp.json()
}

/**
 * GET an endpoint that answers with a file rather than JSON (the CSV export).
 *
 * @param {HostAdapter} host Supplies the session key
 * @param {string} endpoint Path below {@link API_BASE}
 * @returns {Promise<Blob>}
 */
export async function apiBlob(host, endpoint) {
    const resp = await fetch(`${API_BASE}/${endpoint}`, { headers: authHeaders(host) })
    if (!resp.ok) {
        throw await toError(resp)
    }
    return resp.blob()
}

/**
 * Poll `/status` until the daemon answers.
 *
 * After StartPlugin the daemon still has to connect to DSF and register its HTTP
 * endpoints, so the first few requests answer 404 even though the PID is already set.
 *
 * @param {HostAdapter} host Supplies the session key
 * @param {number} [attempts]
 * @param {number} [delay] Milliseconds between attempts
 * @returns {Promise<boolean>} Whether the daemon answered in time
 */
export async function waitForBackend(host, attempts = BACKEND_WAIT_ATTEMPTS, delay = BACKEND_WAIT_INTERVAL) {
    for (let i = 0; i < attempts; i++) {
        try {
            await apiGet(host, 'status')
            return true
        } catch {
            await new Promise(resolve => setTimeout(resolve, delay))
        }
    }
    return false
}

/**
 * Hand a blob to the browser as a download.
 *
 * @param {Blob} blob
 * @param {string} filename
 */
export function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
}
