'use strict'

/**
 * {@link HostAdapter} for DuetWebControl 3.7 (Vue 3.5, Pinia).
 *
 * The 3.6 counterpart (`../ui36/host.js`) talks to a Vuex root store that is a module
 * singleton; 3.7 has per-store composables instead, so the store is resolved on every
 * call rather than captured — which is also what keeps the read reactive.
 *
 * DWC 3.7 externalises `@/stores/*` from the plugin bundle, so this import resolves to
 * DWC's own store at runtime, not to a second copy of Pinia.
 */

import { useMachineStore } from '@/stores/machine'
import { PLUGIN_ID, getPluginEntry } from '../core/backend'

/**
 * @returns {HostAdapter}
 */
export function createHost() {
    // Resolved per call: safe both at plugin-load time and from inside a component,
    // and it is the read that Pinia tracks for the dashboard's backendRunning computed.
    const machine = () => useMachineStore()

    return {
        pluginEntry: () => getPluginEntry(machine().model),
        startBackend: () => Promise.resolve(machine().startSbcPlugin(PLUGIN_ID)),
    }
}
