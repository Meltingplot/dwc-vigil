/**
 * Stub for DWC's Vuex store.
 *
 * In a real DWC environment, this module is provided by DWC itself
 * (imported as '@/store'). This stub exists solely so that Jest can resolve
 * the @/store import via moduleNameMapper.
 *
 * It is deliberately inert: `state` carries no machine module, so the 3.6 host
 * adapter reports `undefined` and ensureBackendRunning() bails out immediately
 * instead of polling.
 *
 * It lives under tests/ so nothing DWC-shaped is ever compiled into a plugin build:
the DWC 3.7 builder is pointed straight at the repo and copies all of src/.
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
