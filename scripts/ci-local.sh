#!/usr/bin/env bash
#
# Run the GitHub Actions CI pipeline (.github/workflows/ci.yml) locally.
#
# Everything is kept inside .ci-local/ (gitignored):
#   .ci-local/venv            Python virtualenv with pytest + pytest-cov
#   .ci-local/DuetWebControl  DWC 3.6 checkout used to build the plugin
#   .ci-local/dist            built plugin ZIPs
#
# Nothing is installed globally and the system Python/Node are left untouched.
#
# Usage:
#   scripts/ci-local.sh [stage ...]
#
# Stages:
#   python      pytest (venv, host Python)
#   matrix      pytest on Python 3.10/3.11/3.12 via Docker (full CI matrix)
#   frontend    npm ci + lint + jest unit + jest integration
#   build       DuetWebControl checkout + npm run build-plugin -> Vigil-<version>.zip
#   all         python + frontend + build  (default)
#
# Env overrides:
#   DWC_REF=v3.6-dev    DuetWebControl ref to build against
#   PYTHON=python3      interpreter used to create the venv

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$ROOT/.ci-local"
VENV="$WORK/venv"
DWC_DIR="$WORK/DuetWebControl"
DWC_REF="${DWC_REF:-v3.6-dev}"
PYTHON="${PYTHON:-python3}"
PY_MATRIX=(3.10 3.11 3.12)

step() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m[ok]\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m[fail]\033[0m %s\n' "$*" >&2; exit 1; }

mkdir -p "$WORK"

stage_python() {
    step "Python tests (venv, $($PYTHON -V))"
    if [ ! -x "$VENV/bin/python" ]; then
        "$PYTHON" -m venv "$VENV"
    fi
    "$VENV/bin/python" -m pip install --quiet --upgrade pip
    "$VENV/bin/python" -m pip install --quiet pytest pytest-cov
    cd "$ROOT"
    PYTHONPATH=dsf "$VENV/bin/python" -m pytest tests/ -v --tb=short --cov --cov-report=term-missing
    ok "Python tests passed"
}

stage_matrix() {
    step "Python matrix via Docker (${PY_MATRIX[*]})"
    command -v docker >/dev/null || die "docker not available"
    for v in "${PY_MATRIX[@]}"; do
        step "Python $v (docker)"
        docker run --rm \
            -v "$ROOT:/src:ro" \
            -w /tmp/work \
            -e PYTHONPATH=dsf \
            "python:$v-slim" \
            bash -c 'set -e
                     cp -r /src/. /tmp/work
                     rm -rf /tmp/work/.ci-local /tmp/work/node_modules
                     find /tmp/work -name __pycache__ -type d -prune -exec rm -rf {} +
                     pip install --quiet --root-user-action=ignore pytest pytest-cov
                     pytest tests/ -v --tb=short --cov --cov-report=term-missing' \
            || die "Python $v failed"
    done
    ok "Python matrix passed"
}

stage_frontend() {
    step "Frontend lint & tests (node $(node -v))"
    cd "$ROOT"
    npm ci
    npm run lint
    npx jest tests/frontend/*.test.js --verbose
    npx jest tests/frontend/integration/ --verbose
    ok "Frontend lint & tests passed"
}

# Fetch (or update) the DuetWebControl checkout at the configured ref.
checkout_dwc() {
    if [ -d "$DWC_DIR/.git" ]; then
        git -C "$DWC_DIR" fetch --depth 1 origin "$DWC_REF"
        git -C "$DWC_DIR" checkout --force FETCH_HEAD
    else
        git clone --depth 1 --branch "$DWC_REF" \
            https://github.com/Duet3D/DuetWebControl.git "$DWC_DIR"
    fi
}

# version.js --write patches plugin.json/package.json; CI does this on a
# throwaway checkout, so locally we snapshot and restore them afterwards.
stamp_version() {
    local backup="$WORK/version-backup"
    mkdir -p "$backup"
    cp "$ROOT/plugin.json" "$ROOT/package.json" "$backup/"
    trap 'cp "$WORK/version-backup/plugin.json" "$WORK/version-backup/package.json" "$ROOT/"' EXIT
    (cd "$ROOT" && node scripts/version.js --write)
}

restore_version() {
    cp "$WORK/version-backup/plugin.json" "$WORK/version-backup/package.json" "$ROOT/"
    trap - EXIT
}

# Report and copy out the ZIP the build produced, and check it is installable.
collect_zip() {
    local zip expected listing
    zip="$(ls -1t "$DWC_DIR"/dist/Vigil-*.zip 2>/dev/null | head -1)"
    [ -n "$zip" ] || die "no plugin ZIP produced"

    mkdir -p "$WORK/dist"
    cp "$zip" "$WORK/dist/"

    step "Plugin ZIP contents"
    unzip -l "$zip"

    listing="$(unzip -Z1 "$zip")"
    step "Verify ZIP layout"
    # DWC installs the ZIP itself, so plugin.json must sit at the root.
    grep -qx 'plugin.json' <<<"$listing" || die "plugin.json is not at the ZIP root"
    grep -qE '^dwc/js/Vigil\..*\.js$' <<<"$listing" || die "ZIP carries no built DWC JS resource"
    grep -qx 'dsf/vigil-daemon.py' <<<"$listing" || die "ZIP is missing the daemon"
    # pytest leaves dsf/__pycache__ behind; CI builds from a clean checkout and
    # never ships it, so a local build must not either.
    if grep -q '__pycache__' <<<"$listing"; then die "ZIP contains __pycache__ entries"; fi

    # dwcVersion/sbcDsfVersion are "auto-major" in the repo; the DWC builder
    # rewrites both to the major.minor of the DuetWebControl checkout used.
    expected="$(node -p 'require("'"$DWC_DIR"'/package.json").version.split(".").slice(0,2).join(".")')"

    step "Verify manifest"
    unzip -p "$zip" plugin.json | node -e '
        let raw = "";
        process.stdin.on("data", (chunk) => { raw += chunk; });
        process.stdin.on("end", () => {
            const manifest = JSON.parse(raw);
            const expected = process.argv[1];
            const fail = (msg) => { console.error(msg); process.exit(1); };
            if (manifest.id !== "Vigil") fail(`id is ${manifest.id}, expected Vigil`);
            if (manifest.dwcVersion !== expected) {
                fail(`dwcVersion is ${manifest.dwcVersion}, expected ${expected}`);
            }
            if (manifest.sbcDsfVersion !== expected) {
                fail(`sbcDsfVersion is ${manifest.sbcDsfVersion}, expected ${expected}`);
            }
            if (manifest.sbcExecutable !== "vigil-daemon.py") {
                fail(`sbcExecutable is ${manifest.sbcExecutable}, expected vigil-daemon.py`);
            }
            if (/auto/.test(manifest.version)) fail("version was not stamped");
            console.log(`version=${manifest.version} dwcVersion=${manifest.dwcVersion} sbcDsfVersion=${manifest.sbcDsfVersion}`);
        });
    ' "$expected" || die "manifest verification failed"

    ok "Built $(basename "$zip") -> .ci-local/dist/"
}

stage_build() {
    step "Build plugin package (DuetWebControl $DWC_REF)"
    checkout_dwc

    # The builder copies dsf/ verbatim; drop the bytecode pytest left behind so
    # the local package matches the one CI builds from a fresh checkout.
    find "$ROOT/dsf" -name __pycache__ -type d -prune -exec rm -rf {} +

    step "Install DuetWebControl dependencies"
    (cd "$DWC_DIR" && npm install)

    stamp_version
    step "Run build-plugin"
    (cd "$DWC_DIR" && npm run build-plugin "$ROOT") || { restore_version; die "plugin build failed"; }
    restore_version

    collect_zip
}

stages=("$@")
[ ${#stages[@]} -eq 0 ] && stages=(all)
for s in "${stages[@]}"; do
    case "$s" in
        all)      stage_python; stage_frontend; stage_build ;;
        python)   stage_python ;;
        matrix)   stage_matrix ;;
        frontend) stage_frontend ;;
        build)    stage_build ;;
        *)        die "unknown stage: $s (python|matrix|frontend|build|all)" ;;
    esac
done

printf '\n'
ok "CI run complete: ${stages[*]}"
