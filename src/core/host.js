'use strict'

/**
 * The seam between Vigil's shared logic and whichever DuetWebControl it runs inside.
 *
 * DWC 3.6 is Vue 2.7 / Vuex 3, DWC 3.7 is Vue 3.5 / Pinia. They differ in how the
 * machine object model is reached and how an SBC plugin is started — and in nothing
 * else this plugin cares about, because all of Vigil's data flows over plain
 * `fetch('/machine/Vigil/…')` calls to the Python daemon, which is DSF's HTTP endpoint
 * mechanism and identical on both generations.
 *
 * So the entire DWC coupling is the two members below. Each UI shell supplies its own
 * implementation (`src/ui36/host.js`, `src/ui37/host.js`) and nothing else in `core/`
 * imports a store.
 *
 * Deliberately raw: no Vue types cross this boundary, and every member is a plain read
 * or a promise — which is what lets `core/` compile against both Vue versions.
 *
 * @typedef {object} HostAdapter
 * @property {() => (object|null|undefined)} pluginEntry
 *   Live read of this plugin's entry in the machine object model (`model.plugins.Vigil`).
 *
 *   MUST read through the store on every call and never return a cached snapshot: the
 *   dashboard's `backendRunning` computed and its `watch` depend on the read being
 *   tracked at call time, so a cached entry would freeze `backendRunning` at its first
 *   value and the recovery banner would never appear.
 *
 *   Returns the entry, `null` when the object model has no entry for this plugin yet,
 *   and `undefined` when there is no machine object model at all (no connection, or a
 *   test host) — {@link module:core/backend.ensureBackendRunning} gives up immediately
 *   on `undefined` rather than polling something that will never appear.
 * @property {() => Promise<void>} startBackend
 *   Ask DSF to start the SBC part of this plugin (`startSbcPlugin('Vigil')`).
 */

export {}
