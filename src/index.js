'use strict'

import { registerRoute } from '@/routes'
import VigilDashboard from './VigilDashboard.vue'

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
