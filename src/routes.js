/**
 * Stub for DWC's route registration API.
 *
 * In a real DWC environment, this module is provided by DWC itself
 * (imported as '@/routes'). This stub exists solely so that:
 *   1. Jest can resolve the @/routes import via moduleNameMapper
 *   2. Integration tests can verify the plugin's registration call
 *
 * This file is NOT included in the plugin ZIP — DWC provides the real one.
 */
export function registerRoute() {
    throw new Error(
        'registerRoute stub called outside DWC. ' +
        'This module is provided by DuetWebControl at runtime.'
    );
}
