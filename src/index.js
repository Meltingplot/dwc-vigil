/**
 * Vigil — entry point compiled by DuetWebControl's plugin builder.
 *
 * Both builders always compile `src/index.js`, so it can only ever name one UI shell.
 * This is the DWC 3.6 one for now; the 3.7 shell takes its place once it exists, and
 * `scripts/stage-dwc36.mjs` generates the 3.6 build its own one-line entry either way.
 */
import './ui36/index'
