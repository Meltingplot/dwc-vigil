#!/usr/bin/env node
/**
 * Compute the plugin version from git tags and commit count.
 *
 * Version scheme:
 *   - HEAD is exactly on a tag `vX.Y.Z`  →  "X.Y.Z"
 *   - N commits past tag `vX.Y.Z`        →  "X.Y.Z-dev.N"
 *   - No version tags exist               →  "<base>-dev.<total-commits>"
 *
 * The base version (used when no tags exist) is read from plugin.json.
 *
 * Usage:
 *   node scripts/version.js          # prints computed version
 *   node scripts/version.js --write  # also updates plugin.json + package.json
 */

'use strict';

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');

function git(cmd) {
    return execSync(cmd, { cwd: ROOT, encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'] }).trim();
}

function computeVersion() {
    const pluginJson = JSON.parse(
        fs.readFileSync(path.join(ROOT, 'plugin.json'), 'utf8')
    );
    const baseVersion = pluginJson.version.replace(/-dev\.\d+$/, '');

    let commitCount;
    try {
        commitCount = parseInt(git('git rev-list --count HEAD'), 10);
    } catch {
        return baseVersion;
    }

    try {
        const describe = git('git describe --tags --match "v[0-9]*" --long');
        const match = describe.match(/^v(.+)-(\d+)-g[0-9a-f]+$/);
        if (match) {
            const tagVersion = match[1];
            const ahead = parseInt(match[2], 10);
            if (ahead === 0) {
                return tagVersion;
            }
            return `${tagVersion}-dev.${ahead}`;
        }
    } catch {
        // No matching tags — fall through
    }

    return `${baseVersion}-dev.${commitCount}`;
}

function writeVersion(version) {
    const pluginPath = path.join(ROOT, 'plugin.json');
    const pluginJson = JSON.parse(fs.readFileSync(pluginPath, 'utf8'));
    pluginJson.version = version;
    fs.writeFileSync(pluginPath, JSON.stringify(pluginJson, null, 2) + '\n');

    const packagePath = path.join(ROOT, 'package.json');
    const packageJson = JSON.parse(fs.readFileSync(packagePath, 'utf8'));
    packageJson.version = version;
    fs.writeFileSync(packagePath, JSON.stringify(packageJson, null, 2) + '\n');
}

const version = computeVersion();
console.log(version);

if (process.argv.includes('--write')) {
    writeVersion(version);
    console.log(`Updated plugin.json and package.json to ${version}`);
}
