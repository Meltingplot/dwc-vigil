'use strict'

/**
 * Value formatting shared by both UI shells.
 *
 * Kept out of the SFCs so the DWC 3.6 and 3.7 components differ only in their
 * templates, and so the formatting itself is unit-tested once without a DOM.
 */

/** Em dash shown wherever a value has not been recorded yet. */
const EMPTY = '—'

/**
 * Format a duration as `1d 2h 3m`.
 *
 * Days and hours are dropped while they are zero, minutes are always shown, so a
 * fresh counter reads "0m" rather than an empty string.
 *
 * @param {number|null|undefined} seconds
 * @returns {string}
 */
export function formatDuration(seconds) {
    if (seconds == null) {
        return EMPTY
    }
    const days = Math.floor(seconds / 86400)
    const hours = Math.floor((seconds % 86400) / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)

    const parts = []
    if (days > 0) parts.push(`${days}d`)
    if (hours > 0 || days > 0) parts.push(`${hours}h`)
    parts.push(`${minutes}m`)
    return parts.join(' ')
}

/**
 * Format a travel distance, scaling mm → m → km.
 *
 * @param {number|null|undefined} mm
 * @returns {string}
 */
export function formatDistance(mm) {
    if (mm == null) {
        return EMPTY
    }
    if (mm >= 1000000) {
        return `${(mm / 1000000).toFixed(2)} km`
    }
    if (mm >= 1000) {
        return `${(mm / 1000).toFixed(2)} m`
    }
    return `${mm.toFixed(0)} mm`
}

/**
 * Format a temperature in degrees Celsius.
 *
 * @param {number|null|undefined} value
 * @returns {string}
 */
export function formatTemp(value) {
    if (value == null) {
        return EMPTY
    }
    return `${value.toFixed(1)} °C`
}

/**
 * Format a voltage.
 *
 * @param {number|null|undefined} value
 * @returns {string}
 */
export function formatVoltage(value) {
    if (value == null) {
        return EMPTY
    }
    return `${value.toFixed(2)} V`
}

/**
 * Format a byte count as KB/MB/GB.
 *
 * @param {number|null|undefined} bytes
 * @returns {string}
 */
export function formatBytes(bytes) {
    if (bytes == null) {
        return EMPTY
    }
    if (bytes >= 1073741824) return `${(bytes / 1073741824).toFixed(1)} GB`
    if (bytes >= 1048576) return `${(bytes / 1048576).toFixed(0)} MB`
    return `${(bytes / 1024).toFixed(0)} KB`
}

/**
 * Format a count with thousands separators.
 *
 * @param {number|null|undefined} value
 * @returns {string}
 */
export function formatNumber(value) {
    if (value == null) {
        return EMPTY
    }
    return value.toLocaleString()
}
