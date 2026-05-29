#!/usr/bin/env bash
# Opt-in installer for beads (bd) CLI.
#
# Beads is required by deep-plan-enhanced for issue tracking + multi-agent
# coordination. This helper installs it via the appropriate package manager
# for the current OS. Re-running is safe (idempotent on Homebrew / `go install`).
#
# Usage:
#   bash scripts/checks/install-beads.sh
#
# Exit codes:
#   0 = bd installed and verified on PATH
#   1 = prerequisite missing (brew / go) or install failed
#   2 = unsupported OS

set -euo pipefail

if command -v bd &> /dev/null; then
    echo "bd already installed: $(bd --version)"
    exit 0
fi

os="$(uname -s)"
case "$os" in
    Darwin)
        if ! command -v brew &> /dev/null; then
            echo "ERROR: Homebrew required. Install from https://brew.sh" >&2
            exit 1
        fi
        echo "Installing beads via Homebrew..."
        brew install beads
        ;;
    Linux)
        if ! command -v go &> /dev/null; then
            echo "ERROR: Go required to install beads on Linux." >&2
            echo "Install Go from https://go.dev/dl/ or download a beads release:" >&2
            echo "  https://github.com/plastic-labs/beads/releases" >&2
            exit 1
        fi
        echo "Installing beads via 'go install'..."
        go install github.com/plastic-labs/beads/cmd/bd@latest
        # Ensure GOPATH/bin is on PATH
        if ! command -v bd &> /dev/null; then
            gopath_bin="$(go env GOPATH)/bin"
            echo "WARNING: bd installed to ${gopath_bin} but not on PATH." >&2
            echo "Add this to your shell rc: export PATH=\"\$PATH:${gopath_bin}\"" >&2
            exit 1
        fi
        ;;
    *)
        echo "ERROR: Unsupported OS '$os'. Manual install:" >&2
        echo "  https://github.com/plastic-labs/beads/releases" >&2
        exit 2
        ;;
esac

# Verify
if ! command -v bd &> /dev/null; then
    echo "ERROR: install completed but bd not on PATH. Restart shell or check install logs." >&2
    exit 1
fi

echo "Installed: $(bd --version)"
