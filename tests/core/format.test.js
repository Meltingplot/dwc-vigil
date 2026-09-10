import { describe, it, expect } from 'vitest'
import {
    formatBytes,
    formatDistance,
    formatDuration,
    formatNumber,
    formatTemp,
    formatVoltage,
} from '../../src/core/format'

const EMPTY = '—'

describe('formatters', () => {
    describe('formatDuration', () => {
        it('drops days and hours while they are zero', () => {
            expect(formatDuration(0)).toBe('0m')
            expect(formatDuration(125)).toBe('2m')
        })

        it('shows hours once a day is on the clock', () => {
            expect(formatDuration(90061)).toBe('1d 1h 1m')
            expect(formatDuration(86400)).toBe('1d 0h 0m')
        })

        it('shows an em dash for a missing value', () => {
            expect(formatDuration(null)).toBe(EMPTY)
            expect(formatDuration(undefined)).toBe(EMPTY)
        })
    })

    describe('formatDistance', () => {
        it('scales mm to m and km', () => {
            expect(formatDistance(950)).toBe('950 mm')
            expect(formatDistance(1500)).toBe('1.50 m')
            expect(formatDistance(2500000)).toBe('2.50 km')
        })
    })

    it('formats temperatures, voltages and byte counts', () => {
        expect(formatTemp(41.25)).toBe('41.3 °C')
        expect(formatVoltage(24.123)).toBe('24.12 V')
        expect(formatBytes(2048)).toBe('2 KB')
        expect(formatBytes(5 * 1048576)).toBe('5 MB')
        expect(formatBytes(3 * 1073741824)).toBe('3.0 GB')
        expect(formatTemp(null)).toBe(EMPTY)
        expect(formatBytes(null)).toBe(EMPTY)
    })

    it('formats counts with thousands separators', () => {
        expect(formatNumber(1234)).toBe((1234).toLocaleString())
        expect(formatNumber(null)).toBe(EMPTY)
    })
})
