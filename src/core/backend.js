'use strict'

/**
 * Helpers for keeping the SBC backend (the Python daemon) running.
 *
 * Background: when a plugin is installed over an existing one, DSF runs
 * UninstallPlugin with the ForUpgrade flag, which stops the running SBC
 * process and drops the plugin from the auto-start list. InstallPlugin then
 * re-registers the plugin with Pid = -1 but never starts it again — DWC only
 * issues StartPlugin when the ZIP was uploaded via "Upload & Start", which is
 * not the case for the "Install Plugin" button on Settings -> Plugins (3.6) or
 * an install wizard run with "start when finished" unticked (3.7).
 *
 * The result is a plugin whose DWC resources are loaded while its backend is
 * dead — exactly what DWC labels "partially started", and why every HTTP
 * endpoint of this plugin returns 404 until the backend is started manually.
 *
 * Everything here works off a {@link HostAdapter} (see ./host.js) rather than a
 * store, so the same code serves the DWC 3.6 and 3.7 shells unchanged.
 */

/** Identifier of this plugin as registered with DSF and DWC. */
export const PLUGIN_ID = 'Vigil'

/** Default delay between attempts while waiting for the object model. */
const DEFAULT_INTERVAL = 1500

/** Default number of attempts before giving up on the object model. */
const DEFAULT_MAX_ATTEMPTS = 20

/**
 * Read this plugin's entry out of a machine object model.
 *
 * `model.plugins` is a Map keyed by plugin ID on both DWC generations; tests may
 * pass a plain object instead.
 *
 * @param {object|null|undefined} model The machine object model
 * @returns {object|null|undefined} The Plugin object, null when the model carries
 *   no entry for this plugin, or undefined when there is no object model at all
 */
export function getPluginEntry(model) {
    if (!model) {
        return undefined
    }
    const plugins = model.plugins
    if (!plugins) {
        return null
    }
    const plugin = plugins instanceof Map ? plugins.get(PLUGIN_ID) : plugins[PLUGIN_ID]
    return plugin || null
}

/**
 * Whether the SBC backend process is running.
 *
 * DSF reports the process ID in `Plugin.pid`: -1 while the plugin is stopped,
 * 0 while it is shutting down, and the real PID while it runs.
 *
 * @param {object|null|undefined} pluginEntry This plugin's object model entry
 * @returns {boolean|null} true/false, or null when the state is not yet known
 */
export function isBackendRunning(pluginEntry) {
    if (!pluginEntry || typeof pluginEntry.pid !== 'number') {
        return null
    }
    return pluginEntry.pid > 0
}

/**
 * Ask DSF to start the SBC part of this plugin.
 *
 * DSF's StartPlugin defaults to SaveState = true, so starting the backend also
 * restores the boot auto-start entry that the upgrade removed.
 *
 * @param {HostAdapter} host DWC host adapter
 * @returns {Promise<void>}
 */
export function startBackend(host) {
    return Promise.resolve(host.startBackend())
}

/**
 * Start the SBC backend if the object model reports it as stopped.
 *
 * The object model may not be populated at the time DWC loads plugin
 * resources, so this polls until the plugin entry shows up. It gives up
 * immediately when the host reports no object model at all (`undefined`),
 * which is the case outside a connected DWC — e.g. in unit tests.
 *
 * @param {HostAdapter} host DWC host adapter
 * @param {object} [options] Polling options
 * @param {number} [options.interval] Delay between attempts in ms
 * @param {number} [options.maxAttempts] Attempts before giving up
 * @returns {Promise<boolean>} Whether a start was issued
 */
export function ensureBackendRunning(host, options = {}) {
    const interval = options.interval || DEFAULT_INTERVAL
    const maxAttempts = options.maxAttempts || DEFAULT_MAX_ATTEMPTS

    if (!host || typeof host.pluginEntry !== 'function') {
        return Promise.resolve(false)
    }

    return new Promise(resolve => {
        let attempts = 0

        const check = () => {
            attempts++

            let entry
            try {
                entry = host.pluginEntry()
            } catch {
                entry = undefined
            }

            if (entry === undefined) {
                // No machine object model — nothing to inspect and nothing to start
                resolve(false)
                return
            }

            const running = isBackendRunning(entry)

            if (running === true) {
                resolve(false)
                return
            }

            if (running === false) {
                startBackend(host).then(
                    () => resolve(true),
                    err => {
                        // eslint-disable-next-line no-console
                        console.warn(`[${PLUGIN_ID}] failed to start the SBC backend:`, err)
                        resolve(false)
                    }
                )
                return
            }

            if (attempts >= maxAttempts) {
                resolve(false)
                return
            }
            setTimeout(check, interval)
        }

        check()
    })
}
