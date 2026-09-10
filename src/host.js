'use strict'

/**
 * {@link HostAdapter} for DuetWebControl 3.6 (Vue 2.7, Vuex 3).
 *
 * DWC 3.6 exposes a single Vuex root store as a module singleton, with a namespaced
 * `machine` module holding the object model. The 3.7 counterpart talks to the Pinia
 * machine store instead; nothing else about the adapter differs.
 */

import store from '@/store'
import { PLUGIN_ID, getPluginEntry } from './core/backend'

/**
 * @returns {HostAdapter}
 */
export function createHost() {
    return {
        // Read through the store on every call rather than caching: Vue 2.7 tracks the
        // access at read time, which is what keeps the dashboard's backendRunning
        // computed (and its watcher) live when DSF reports a new PID.
        pluginEntry: () => getPluginEntry(store.state && store.state.machine && store.state.machine.model),
        startBackend: () => Promise.resolve(store.dispatch('machine/startSbcPlugin', PLUGIN_ID)),
    }
}
