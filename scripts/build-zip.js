#!/usr/bin/env node
/**
 * Build script: assembles the DWC plugin ZIP.
 *
 * The ZIP structure matches what DWC expects when installing a plugin:
 *
 *   Vigil-<version>.zip
 *   ├── plugin.json
 *   ├── dsf/
 *   │   ├── vigil-daemon.py
 *   │   ├── vigil_tracker.py
 *   │   ├── vigil_persistence.py
 *   │   ├── vigil_time.py
 *   │   └── vigil_api.py
 *   └── dwc/
 *       └── Vigil/
 *           └── ... (source files)
 *
 * For a full production build, use DWC's build-plugin command instead:
 *   cd DuetWebControl && npm run build-plugin /path/to/dwc-vigil
 *
 * This script creates a standalone ZIP for CI artifact purposes.
 */

'use strict';

const fs = require('fs');
const path = require('path');
const archiver = require('archiver');
const { execSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const pluginJson = JSON.parse(fs.readFileSync(path.join(ROOT, 'plugin.json'), 'utf8'));
const pluginId = pluginJson.id;

// Compute version from git without modifying source files
let version;
try {
    version = execSync('node scripts/version.js', { cwd: ROOT, encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] }).split('\n')[0];
} catch {
    version = pluginJson.version;
}
const stampedPluginJson = { ...pluginJson, version };
console.log(`Building version ${version}`);

const DIST_DIR = path.join(ROOT, 'dist');
const ZIP_NAME = `${pluginId}-${version}.zip`;
const ZIP_PATH = path.join(DIST_DIR, ZIP_NAME);

fs.mkdirSync(DIST_DIR, { recursive: true });

const output = fs.createWriteStream(ZIP_PATH);
const archive = archiver('zip', { zlib: { level: 9 } });

output.on('close', () => {
    const sizeKB = (archive.pointer() / 1024).toFixed(1);
    console.log(`Built ${ZIP_NAME} (${sizeKB} KB)`);
});

archive.on('error', (err) => {
    console.error('Archive error:', err);
    process.exit(1);
});

archive.pipe(output);

// plugin.json at root (with computed version)
archive.append(JSON.stringify(stampedPluginJson, null, 2) + '\n', { name: 'plugin.json' });

// dsf/ — Python backend files
const dsfDir = path.join(ROOT, 'dsf');
const dsfFiles = fs.readdirSync(dsfDir).filter(f => f.endsWith('.py'));
for (const file of dsfFiles) {
    archive.file(path.join(dsfDir, file), { name: `dsf/${file}` });
}

// dwc/ — Frontend source files (for DWC's plugin loader)
// Exclude test stubs (__mocks__/, routes.js) that only exist for Jest.
archive.glob('**/*', {
    cwd: path.join(ROOT, 'src'),
    ignore: ['__mocks__/**', 'routes.js']
}, { prefix: 'dwc/src/' });

archive.finalize();
