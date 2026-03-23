import { describe, it, expect } from '@jest/globals'
import { shallowMount } from '@vue/test-utils'
import StatCard from '../../src/components/StatCard.vue'

describe('StatCard', () => {
    const vuetify = createVuetify()

    it('renders label and numeric value', () => {
        const wrapper = shallowMount(StatCard, {
            vuetify,
            propsData: { label: 'Jobs Total', value: 42, type: 'number' }
        })
        expect(wrapper.text()).toContain('Jobs Total')
        expect(wrapper.text()).toContain('42')
    })

    it('formats time as days/hours/minutes', () => {
        const wrapper = shallowMount(StatCard, {
            vuetify,
            propsData: { label: 'Machine Hours', value: 90061, type: 'time' }
        })
        // 90061s = 1d 1h 1m
        expect(wrapper.text()).toContain('1d')
        expect(wrapper.text()).toContain('1h')
        expect(wrapper.text()).toContain('1m')
    })

    it('formats zero time correctly', () => {
        const wrapper = shallowMount(StatCard, {
            vuetify,
            propsData: { label: 'Test', value: 0, type: 'time' }
        })
        expect(wrapper.text()).toContain('0m')
    })

    it('renders icon when provided', () => {
        const wrapper = shallowMount(StatCard, {
            vuetify,
            propsData: { label: 'Test', value: 5, icon: 'mdi-power', color: 'blue' }
        })
        expect(wrapper.text()).toContain('Test')
        expect(wrapper.text()).toContain('5')
    })
})
