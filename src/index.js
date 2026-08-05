'use strict'

import { registerRoute } from '@/routes'
import store from '@/store'
import VigilDashboard from './VigilDashboard.vue'
import { ensureBackendRunning } from './backend'

registerRoute(VigilDashboard, {
    Plugins: {
        Vigil: {
            icon: 'mdi-chart-box-outline',
            caption: 'Vigil',
            translated: true,
            path: '/Vigil'
        }
    }
})

// Installing over an existing version makes DSF stop the old SBC process
// without starting the new one, which leaves the plugin "partially started"
// and all of its HTTP endpoints unreachable. Recover from that as soon as DWC
// loads our resources.
ensureBackendRunning(store)
