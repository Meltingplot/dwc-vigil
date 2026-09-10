import Vue from 'vue'
import Vuetify from 'vuetify'

Vue.use(Vuetify)
Vue.config.productionTip = false

global.createVuetify = () => new Vuetify()

document.body.setAttribute('data-app', 'true')
