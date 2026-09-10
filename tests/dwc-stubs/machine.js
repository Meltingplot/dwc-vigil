/**
 * Stand-in for DWC 3.7's `@/stores/machine` under vitest.
 *
 * dwc-plugin-test-kit ships a stub for this store, but it only covers `model`,
 * `isConnected`, `sendCode` and `getFileList` — not `startSbcPlugin`, which is the one
 * machine-store action Vigil actually calls. So this replaces the kit's alias with a
 * stub that keeps the kit's shared state (`dwc.model`, fed by `setModel(...)`) and adds
 * the recording of started SBC plugins that the backend-recovery tests assert on.
 */
import { dwc } from 'dwc-plugin-test-kit'

const started = []

/** SBC plugin IDs that the code under test asked DSF to start, in order. */
export function startedSbcPlugins() {
    return started
}

/** Clear the record — call alongside the kit's own resetDwc(). */
export function resetSbcPlugins() {
    started.length = 0
}

/** Set to make the next startSbcPlugin call reject, as DSF does when it refuses. */
let startFailure = null

export function failNextSbcPluginStart(error) {
    startFailure = error
}

export function useMachineStore() {
    return {
        get model() { return dwc.model },
        get isConnected() { return dwc.connected },
        async startSbcPlugin(plugin) {
            if (startFailure) {
                const error = startFailure
                startFailure = null
                throw error
            }
            started.push(plugin)
        },
    }
}
