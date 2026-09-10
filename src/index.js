/**
 * Vigil — entry point compiled by DuetWebControl's plugin builder.
 *
 * Both builders always compile `src/index.js`, so it can only ever name one UI shell.
 * This is the DWC 3.7 one, because 3.7's builder is pointed straight at the repo;
 * `scripts/stage-dwc36.mjs` generates the 3.6 build its own one-line entry naming
 * `./ui36/index` instead.
 */
import './ui37/index'
