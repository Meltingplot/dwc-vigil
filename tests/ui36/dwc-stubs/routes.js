/**
 * Stub for DWC's route registration API.
 *
 * In a real DWC environment, this module is provided by DWC itself
 * (imported as '@/routes'). This stub exists solely so that:
 *   1. Jest can resolve the @/routes import via moduleNameMapper
 *   2. Integration tests can verify the plugin's registration call
 *
 * It lives under tests/ so nothing DWC-shaped is ever compiled into a plugin build:
the DWC 3.7 builder is pointed straight at the repo and copies all of src/.
 */
export function registerRoute() {
    throw new Error(
        'registerRoute stub called outside DWC. ' +
        'This module is provided by DuetWebControl at runtime.'
    );
}
