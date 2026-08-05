/**
 * Stub for DWC's Vuex store.
 *
 * In a real DWC environment, this module is provided by DWC itself
 * (imported as '@/store'). This stub exists solely so that Jest can resolve
 * the @/store import via moduleNameMapper.
 *
 * It is deliberately inert: `state` carries no machine module, so
 * ensureBackendRunning() bails out immediately instead of polling.
 *
 * This file is NOT included in the plugin ZIP — DWC provides the real one.
 */
export default {
    state: {},
    dispatch() {
        return Promise.reject(
            new Error(
                'store.dispatch stub called outside DWC. ' +
                'This module is provided by DuetWebControl at runtime.'
            )
        )
    }
}
