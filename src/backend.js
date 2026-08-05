'use strict'

/**
 * Helpers for keeping the SBC backend (the Python daemon) running.
 *
 * Background: when a plugin is installed over an existing one, DSF runs
 * UninstallPlugin with the ForUpgrade flag, which stops the running SBC
 * process and drops the plugin from the auto-start list. InstallPlugin then
 * re-registers the plugin with Pid = -1 but never starts it again — DWC only
 * issues StartPlugin when the ZIP was uploaded via "Upload & Start", which is
 * not the case for the "Install Plugin" button on Settings -> Plugins.
 *
 * The result is a plugin whose DWC resources are loaded while its backend is
 * dead — exactly what DWC labels "partially started", and why every HTTP
 * endpoint of this plugin returns 404 until the backend is started manually.
 */

/** Identifier of this plugin as registered with DSF and DWC. */
export const PLUGIN_ID = 'Vigil'

/** Default delay between attempts while waiting for the object model. */
const DEFAULT_INTERVAL = 1500

/** Default number of attempts before giving up on the object model. */
const DEFAULT_MAX_ATTEMPTS = 20

/**
 * Read this plugin's entry from the machine object model.
 *
 * In DWC 3.6 `state.plugins` is a Map keyed by plugin ID; tests may use a
 * plain object instead.
 *
 * @param {object} modelState State of the `machine/model` Vuex module
 * @returns {object|null} The Plugin object, or null if not present
 */
export function getPluginEntry(modelState) {
    const plugins = modelState && modelState.plugins
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
 * @param {object} modelState State of the `machine/model` Vuex module
 * @returns {boolean|null} true/false, or null when the state is not yet known
 */
export function isBackendRunning(modelState) {
    const plugin = getPluginEntry(modelState)
    if (!plugin || typeof plugin.pid !== 'number') {
        return null
    }
    return plugin.pid > 0
}

/**
 * Ask DSF to start the SBC part of this plugin.
 *
 * DSF's StartPlugin defaults to SaveState = true, so starting the backend also
 * restores the boot auto-start entry that the upgrade removed.
 *
 * @param {object} store Root Vuex store
 * @returns {Promise<void>}
 */
export function startBackend(store) {
    return Promise.resolve(store.dispatch('machine/startSbcPlugin', PLUGIN_ID))
}

/**
 * Start the SBC backend if the object model reports it as stopped.
 *
 * The object model may not be populated at the time DWC loads plugin
 * resources, so this polls until the plugin entry shows up. It gives up
 * immediately when there is no machine module at all (e.g. in unit tests).
 *
 * @param {object} store Root Vuex store
 * @param {object} [options] Polling options
 * @param {number} [options.interval] Delay between attempts in ms
 * @param {number} [options.maxAttempts] Attempts before giving up
 * @returns {Promise<boolean>} Whether a start was issued
 */
export function ensureBackendRunning(store, options = {}) {
    const interval = options.interval || DEFAULT_INTERVAL
    const maxAttempts = options.maxAttempts || DEFAULT_MAX_ATTEMPTS

    const machine = store && store.state && store.state.machine
    if (!machine || !machine.model) {
        // No machine module — nothing to inspect and nothing to start
        return Promise.resolve(false)
    }

    return new Promise(resolve => {
        let attempts = 0

        const check = () => {
            attempts++

            let running = null
            try {
                running = isBackendRunning(store.state.machine.model)
            } catch {
                running = null
            }

            if (running === true) {
                resolve(false)
                return
            }

            if (running === false) {
                startBackend(store).then(
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
