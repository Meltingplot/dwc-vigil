'use strict'

/**
 * Talking to the Vigil daemon.
 *
 * The daemon registers its HTTP endpoints with DSF (`cmd.add_http_endpoint`), which
 * serves them under `/machine/<pluginId>/…` on the very origin DWC itself is served
 * from. That is identical on DSF 3.6 and 3.7 and involves no DWC API at all, which is
 * why every call in here is a plain `fetch` and this module is shared verbatim by both
 * UI shells.
 */

/** Base path DSF serves this plugin's HTTP endpoints under. */
export const API_BASE = '/machine/Vigil'

/** How long to wait for the daemon to register its endpoints after a start. */
export const BACKEND_WAIT_ATTEMPTS = 15

/** Delay between endpoint probes while waiting for the daemon. */
export const BACKEND_WAIT_INTERVAL = 1000

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
 * @param {string} endpoint Path below {@link API_BASE}, e.g. `history?days=30`
 * @returns {Promise<object>} Parsed response body
 */
export async function apiGet(endpoint) {
    const resp = await fetch(`${API_BASE}/${endpoint}`)
    if (!resp.ok) {
        throw await toError(resp)
    }
    return resp.json()
}

/**
 * POST JSON to an endpoint.
 *
 * @param {string} endpoint Path below {@link API_BASE}
 * @param {object} [data] Request body
 * @returns {Promise<object>} Parsed response body
 */
export async function apiPost(endpoint, data = {}) {
    const resp = await fetch(`${API_BASE}/${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
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
 * @param {string} endpoint Path below {@link API_BASE}
 * @returns {Promise<Blob>}
 */
export async function apiBlob(endpoint) {
    const resp = await fetch(`${API_BASE}/${endpoint}`)
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
 * @param {number} [attempts]
 * @param {number} [delay] Milliseconds between attempts
 * @returns {Promise<boolean>} Whether the daemon answered in time
 */
export async function waitForBackend(attempts = BACKEND_WAIT_ATTEMPTS, delay = BACKEND_WAIT_INTERVAL) {
    for (let i = 0; i < attempts; i++) {
        try {
            await apiGet('status')
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
