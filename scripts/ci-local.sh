#!/usr/bin/env bash
#
# Run the GitHub Actions CI pipeline (.github/workflows/ci.yml) locally.
#
# Everything is kept inside .ci-local/ (gitignored):
#   .ci-local/venv                 Python virtualenv with pytest + pytest-cov
#   .ci-local/DuetWebControl-36    DWC 3.6 checkout used for the 3.6 package
#   .ci-local/stage-36            staged 3.6 source tree (scripts/stage-dwc36.mjs)
#   .ci-local/dist                 built plugin ZIPs, one per DWC generation
#   .ci-local/version-backup       plugin.json / package.json snapshots
#
# Nothing is installed globally and the system Python/Node are left untouched.
#
# Usage:
#   scripts/ci-local.sh [stage ...]
#
# Stages:
#   python      pytest (venv, host Python)
#   matrix      pytest on Python 3.10/3.11/3.12 via Docker (full CI matrix)
#   frontend    npm ci + lint + vitest (core, ui37) + jest (ui36)
#   build36     DWC 3.6 checkout + stage + build-plugin-pkg -> Vigil-<version>-dwc36.zip
#   build       every build stage (currently just build36)
#   all         python + frontend + build  (default)
#
# Env overrides:
#   DWC36_REF=v3.6-dev  DuetWebControl ref the 3.6 package is built against
#   PYTHON=python3      interpreter used to create the venv

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$ROOT/.ci-local"
VENV="$WORK/venv"
DIST="$WORK/dist"
DWC36_DIR="$WORK/DuetWebControl-36"
DWC36_REF="${DWC36_REF:-v3.6-dev}"
STAGE36="$WORK/stage-36"
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
    # src/core/ and src/ui37/ — Vue 3, vitest, dwc-plugin-test-kit
    npm test
    # src/ui36/ — Vue 2.7, Jest, in its own nested project with its own lockfile
    (cd "$ROOT/tests/ui36" && npm ci)
    npm run test:ui36
    ok "Frontend lint & tests passed"
}

# Fetch (or update) a DuetWebControl checkout at the given ref.
checkout_dwc() {
    local dir="$1" ref="$2"
    if [ -d "$dir/.git" ]; then
        git -C "$dir" fetch --depth 1 origin "$ref"
        git -C "$dir" checkout --force FETCH_HEAD
    else
        git clone --depth 1 --branch "$ref" \
            https://github.com/Duet3D/DuetWebControl.git "$dir"
    fi
}

# major.minor of a DuetWebControl checkout — what "auto-major" resolves to.
dwc_major_minor() {
    node -p 'require(process.argv[1] + "/package.json").version.split(".").slice(0,2).join(".")' "$1"
}

# version.js --write patches plugin.json/package.json; CI does this on a throwaway
# checkout, so locally we snapshot and restore them afterwards. Stamped once before
# the first build stage so every generation's ZIP carries the same version.
VERSION=""
stamp_version() {
    [ -n "$VERSION" ] && return 0
    local backup="$WORK/version-backup"
    mkdir -p "$backup"
    cp "$ROOT/plugin.json" "$ROOT/package.json" "$backup/"
    trap 'restore_version' EXIT
    (cd "$ROOT" && node scripts/version.js --write >/dev/null)
    VERSION="$(node -p 'require("'"$ROOT"'/plugin.json").version')"
    step "Stamped version $VERSION"
}

restore_version() {
    [ -f "$WORK/version-backup/plugin.json" ] || return 0
    cp "$WORK/version-backup/plugin.json" "$WORK/version-backup/package.json" "$ROOT/"
}

# pytest leaves dsf/__pycache__ behind and every builder copies dsf/ verbatim, so a
# local package would ship bytecode that CI's fresh checkout never has.
strip_pycache() {
    find "$ROOT/dsf" -name __pycache__ -type d -prune -exec rm -rf {} +
}

# Check a built ZIP is installable, then copy it into .ci-local/dist under its
# generation-specific name.
#   collect_zip <built-zip> <expected dwcVersion major.minor> <dist filename>
collect_zip() {
    local zip="$1" expected="$2" name="$3" listing
    [ -f "$zip" ] || die "no plugin ZIP at $zip"

    step "Plugin ZIP contents ($(basename "$zip"))"
    unzip -l "$zip"

    listing="$(unzip -Z1 "$zip")"
    step "Verify ZIP layout"
    # DWC installs the ZIP itself, so plugin.json must sit at the root.
    grep -qx 'plugin.json' <<<"$listing" || die "plugin.json is not at the ZIP root"
    # 3.6 (webpack) emits Vigil.<hash>.js, 3.7 (Vite) emits Vigil-<hash>.js
    grep -qE '^dwc/js/Vigil[.-].*\.js$' <<<"$listing" || die "ZIP carries no built DWC JS resource"
    grep -qx 'dsf/vigil-daemon.py' <<<"$listing" || die "ZIP is missing the daemon"
    if grep -q '__pycache__' <<<"$listing"; then die "ZIP contains __pycache__ entries"; fi
    # The 3.7 builder writes a sourcemap archive next to the package; one that slipped
    # into the staged tree would install as an unusable ZIP-in-ZIP.
    if grep -qE '\.zip$' <<<"$listing"; then die "ZIP contains a nested *.zip entry"; fi

    step "Verify manifest"
    unzip -p "$zip" plugin.json | node -e '
        let raw = "";
        process.stdin.on("data", (chunk) => { raw += chunk; });
        process.stdin.on("end", () => {
            const manifest = JSON.parse(raw);
            const expected = process.argv[1];
            const fail = (msg) => { console.error(msg); process.exit(1); };
            if (manifest.id !== "Vigil") fail(`id is ${manifest.id}, expected Vigil`);
            // dwcVersion/sbcDsfVersion are "auto-major" in the repo; each builder
            // rewrites both to the major.minor of the DWC checkout doing the build.
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
            // build-plugin-pkg (both generations) is what populates these; the plain
            // build-plugin does not, and DSF needs them to know what to install.
            for (const key of ["dwcFiles", "dsfFiles"]) {
                if (!Array.isArray(manifest[key]) || manifest[key].length === 0) {
                    fail(`${key} is missing or empty — was the package built with build-plugin-pkg?`);
                }
            }
            if (!manifest.dsfFiles.includes("vigil-daemon.py")) {
                fail(`dsfFiles does not list vigil-daemon.py: ${manifest.dsfFiles.join(", ")}`);
            }
            console.log(`version=${manifest.version} dwcVersion=${manifest.dwcVersion} sbcDsfVersion=${manifest.sbcDsfVersion}`);
        });
    ' "$expected" || die "manifest verification failed"

    mkdir -p "$DIST"
    cp "$zip" "$DIST/$name"
    ok "Built $name -> .ci-local/dist/"
}

stage_build36() {
    step "Build DWC 3.6 package (DuetWebControl $DWC36_REF)"
    checkout_dwc "$DWC36_DIR" "$DWC36_REF"

    step "Install DuetWebControl 3.6 dependencies"
    (cd "$DWC36_DIR" && npm install)

    step "Compile-check the DWC 3.6 SFCs"
    (cd "$ROOT" && DWC36_DIR="$DWC36_DIR" npm run --silent check-ui36)

    strip_pycache
    stamp_version

    step "Stage the DWC 3.6 source tree"
    (cd "$ROOT" && node scripts/stage-dwc36.mjs "$STAGE36")

    # The 3.6 builder removes its copy under src/plugins/ only on success, and picks up
    # whatever is in dist/ afterwards — so start both from a known state.
    rm -rf "$DWC36_DIR/src/plugins/Vigil"
    rm -f "$DWC36_DIR"/dist/Vigil-*.zip

    step "Run build-plugin-pkg on the staged tree"
    (cd "$DWC36_DIR" && npm run build-plugin-pkg -- "$STAGE36") || die "DWC 3.6 plugin build failed"

    collect_zip "$DWC36_DIR/dist/Vigil-$VERSION.zip" "$(dwc_major_minor "$DWC36_DIR")" "Vigil-$VERSION-dwc36.zip"
}

stage_build() {
    stage_build36
}

stages=("$@")
[ ${#stages[@]} -eq 0 ] && stages=(all)
for s in "${stages[@]}"; do
    case "$s" in
        all)      stage_python; stage_frontend; stage_build ;;
        python)   stage_python ;;
        matrix)   stage_matrix ;;
        frontend) stage_frontend ;;
        build36)  stage_build36 ;;
        build)    stage_build ;;
        *)        die "unknown stage: $s (python|matrix|frontend|build36|build|all)" ;;
    esac
done

printf '\n'
ok "CI run complete: ${stages[*]}"
