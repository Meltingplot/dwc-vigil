'use strict'

/**
 * Vigil — DuetWebControl 3.7 entry point.
 *
 * Differences from the 3.6 entry (`../ui36/index.js`), all forced by what each plugin
 * API offers:
 *
 *  - `registerRoute` comes from `@/plugins`, not `@/routes`.
 *  - 3.7 emits `dwcPluginUnloaded` when a plugin is stopped from Settings → Plugins, so
 *    the menu entry can be taken down again without a page reload. 3.6 has no such
 *    event and nothing to unregister.
 */

import { registerRoute, unregisterRoute } from '@/plugins'
import Events from '@/utils/events'
import VigilDashboard from './VigilDashboard.vue'
import { PLUGIN_ID, ensureBackendRunning } from '../core/backend'
import { createHost } from './host'

const ROUTE_PATH = '/Vigil'

registerRoute(VigilDashboard, {
    Plugins: {
        Vigil: {
            icon: 'mdi-chart-box-outline',
            caption: 'Vigil',
            // The caption is display text, not an i18n key — same meaning on both
            // generations. Adding translations later means dropping this flag and
            // registering messages under `plugins.Vigil.*` instead.
            translated: true,
            path: ROUTE_PATH
        }
    }
})

// Installing over an existing version makes DSF stop the old SBC process without
// starting the new one, which leaves the plugin "partially started" and all of its
// HTTP endpoints unreachable. 3.7's install wizard has a "start when finished"
// checkbox that defaults to off, so this is if anything easier to hit than on 3.6.
ensureBackendRunning(createHost())

function onPluginUnloaded(id) {
    if (id === PLUGIN_ID) {
        unregisterRoute(ROUTE_PATH)
        Events.off('dwcPluginUnloaded', onPluginUnloaded)
    }
}
Events.on('dwcPluginUnloaded', onPluginUnloaded)
