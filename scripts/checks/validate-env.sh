#!/usr/bin/env bash
# Environment validator for deep-plan plugin
#
# SECURITY: This script NEVER outputs sensitive credentials.
# - API keys are checked with [ -n "$VAR" ] which only tests existence, never echoes
# - ADC validation discards token output (> /dev/null), only exit code is used
# - JSON output contains only auth METHOD ("api_key", "vertex_ai_adc") or boolean, never actual secrets
#
# Checks:
# 1. uv is installed (REQUIRED - all Python execution uses uv)
# 2. Gemini auth:
#    - GEMINI_API_KEY (AI Studio API) OR
#    - ADC + GCP project (Vertex AI API)
#      Project source: config.json → gcloud config → GOOGLE_CLOUD_PROJECT env
# 3. OPENAI_API_KEY is set (for ChatGPT)
# 4. Test actual client construction (calls test_llm_clients.py)
#
# Exit codes:
# 0 = plugin can function (may have warnings about missing LLM credentials)
# 1 = reserved (previously: missing Gemini — now a warning)
# 2 = reserved (previously: missing OpenAI — now a warning)
# 3 = could not locate plugin root (fatal)
# 5 = uv not installed (fatal)
#
# Design: Missing LLM credentials are WARNINGS, not errors, because the workflow
# can fall back to Claude Opus subagent review. Only truly fatal issues (uv missing,
# plugin root not found) produce errors and non-zero exits.

set -euo pipefail

# Derive plugin root from script location
# This works regardless of how the plugin was installed (cache, dev mode, etc.)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PLUGIN_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Sanity check: verify we found the right place
if [[ ! -f "$PLUGIN_ROOT/config.json" ]] && [[ ! -f "$PLUGIN_ROOT/SKILL.md" ]]; then
    echo '{"valid": false, "errors": ["Could not locate plugin root from script location. Expected config.json or skills/ at: '"$PLUGIN_ROOT"'"], "warnings": [], "gemini_auth": null, "openai_auth": false}'
    exit 3
fi

# Initialize output arrays
errors=()
warnings=()
gemini_auth="null"
openai_auth="false"

# Check 1: uv must be installed
if ! command -v uv &> /dev/null; then
    echo '{"valid": false, "errors": ["uv not installed. Install from https://docs.astral.sh/uv/"], "warnings": [], "gemini_auth": null, "openai_auth": false}'
    exit 5
fi

# Check: bd (beads) — REQUIRED for audit trail + multi-agent coordination
if command -v bd &> /dev/null; then
    beads_available="true"
else
    beads_available="false"
    case "$(uname -s)" in
        Darwin) install_hint="brew install beads  (or: bash ${SCRIPT_DIR}/install-beads.sh)" ;;
        Linux)  install_hint="go install github.com/plastic-labs/beads/cmd/bd@latest  (or: bash ${SCRIPT_DIR}/install-beads.sh)" ;;
        *)      install_hint="see https://github.com/plastic-labs/beads/releases" ;;
    esac
    errors+=("bd (beads) required but not on PATH. Install: ${install_hint}")
fi

# Load config values
config_file="${PLUGIN_ROOT}/config.json"
alert_if_missing="true"
config_gcp_project=""
config_gcp_location=""
gemini_model=""
openai_model=""

if [ -f "$config_file" ]; then
    # Parse values from config using jq
    alert_if_missing=$(jq -r '.external_review.alert_if_missing // true' "$config_file" 2>/dev/null || echo "true")

    # Get GCP project from config (null becomes empty string)
    config_gcp_project=$(jq -r '.vertex_ai.project // empty' "$config_file" 2>/dev/null || echo "")

    # Get GCP location from config (null becomes empty string)
    config_gcp_location=$(jq -r '.vertex_ai.location // empty' "$config_file" 2>/dev/null || echo "")

    # Get model names from config
    gemini_model=$(jq -r '.models.gemini // empty' "$config_file" 2>/dev/null || echo "")
    openai_model=$(jq -r '.models.chatgpt // empty' "$config_file" 2>/dev/null || echo "")
fi

# Get GCP project from gcloud config (if gcloud is available)
gcloud_gcp_project=""
if command -v gcloud &> /dev/null; then
    gcloud_gcp_project=$(gcloud config get-value project 2>/dev/null || echo "")
fi

# Resolve GCP project: config.json → gcloud config → env var
# Resolve GCP location: config.json → env var (no default - must be explicitly set for ADC)
gcp_project="${config_gcp_project:-${gcloud_gcp_project:-${GOOGLE_CLOUD_PROJECT:-}}}"
gcp_location="${config_gcp_location:-${GOOGLE_CLOUD_LOCATION:-}}"

# Check 2: Gemini auth
# Priority: API key (AI Studio) > ADC + Project (Vertex AI)
# SECURITY: We only check if API key EXISTS ([ -n ] test), never echo its value
if [ -n "${GEMINI_API_KEY:-}" ]; then
    gemini_auth='"api_key"'
else
    # Check for ADC (either explicit path or default location)
    adc_path="${HOME}/.config/gcloud/application_default_credentials.json"
    has_adc="false"
    if [ -n "${GOOGLE_APPLICATION_CREDENTIALS:-}" ] && [ -f "${GOOGLE_APPLICATION_CREDENTIALS}" ]; then
        has_adc="true"
    elif [ -f "$adc_path" ]; then
        has_adc="true"
    fi

    if [ "$has_adc" = "true" ]; then
        # ADC exists - check if GCP project AND location are set (both required for Vertex AI)
        if [ -z "$gcp_project" ]; then
            gemini_auth='"adc_no_project"'
            if [ "$alert_if_missing" = "true" ]; then
                warnings+=("Gemini: ADC found but no GCP project. Set vertex_ai.project in $config_file or export GOOGLE_CLOUD_PROJECT=your-project-id")
            fi
        elif [ -z "$gcp_location" ]; then
            gemini_auth='"adc_no_location"'
            if [ "$alert_if_missing" = "true" ]; then
                warnings+=("Gemini: ADC found but no GCP location. Set vertex_ai.location in $config_file or export GOOGLE_CLOUD_LOCATION=your-region (e.g., us-central1)")
            fi
        else
            # ADC, project, and location exist - verify credentials are still valid
            # SECURITY: Token output discarded (> /dev/null), only exit code used
            if gcloud auth application-default print-access-token > /dev/null 2>&1; then
                gemini_auth='"vertex_ai_adc"'
            else
                gemini_auth='"adc_stale"'
                if [ "$alert_if_missing" = "true" ]; then
                    warnings+=("Gemini: ADC credentials are stale. Run: gcloud auth application-default login")
                fi
            fi
        fi
    else
        # No auth found — recoverable, workflow can use Opus subagent for review
        if [ "$alert_if_missing" = "true" ]; then
            warnings+=("Gemini: not configured. Options: 1) export GEMINI_API_KEY=key 2) export GOOGLE_CLOUD_PROJECT=proj && gcloud auth application-default login")
        fi
    fi
fi

# Check 3: OpenAI API key
# SECURITY: We only check if API key EXISTS ([ -n ] test), never echo its value
if [ -n "${OPENAI_API_KEY:-}" ]; then
    openai_auth="true"
else
    if [ "$alert_if_missing" = "true" ]; then
        warnings+=("OpenAI: OPENAI_API_KEY not set")
    fi
fi

# Check 4: Test actual client construction AND model access
# Only run if we have potential auth methods to test AND models configured
test_script="${SCRIPT_DIR}/test_llm_clients.py"
client_test_results=""

if [ -f "$test_script" ]; then
    test_args=""

    # Build test arguments based on what auth we found
    # Now includes model name to verify model access, not just auth
    if [ -n "${GEMINI_API_KEY:-}" ] && [ -n "$gemini_model" ]; then
        test_args="--gemini-api-key $gemini_model"
    elif [ "$gemini_auth" = '"vertex_ai_adc"' ] && [ -n "$gcp_project" ] && [ -n "$gemini_model" ]; then
        test_args="--vertex-ai $gcp_project $gcp_location $gemini_model"
    fi

    if [ -n "${OPENAI_API_KEY:-}" ] && [ -n "$openai_model" ]; then
        test_args="$test_args --openai $openai_model"
    fi

    # Run the test if we have any auth to test
    if [ -n "$test_args" ]; then
        client_test_results=$(uv run --directory "$PLUGIN_ROOT" "$test_script" $test_args 2>&1) || true

        # Parse test results and add errors if tests failed
        # NOTE: jq's // operator triggers on BOTH null AND false, so we use explicit checks
        if [ -n "$client_test_results" ]; then
            # Check for Gemini failures (check both api_key and vertex_ai results)
            if echo "$client_test_results" | jq -e '.gemini_api_key' > /dev/null 2>&1; then
                gemini_success=$(echo "$client_test_results" | jq -r '.gemini_api_key.success' 2>/dev/null)
                if [ "$gemini_success" = "false" ]; then
                    gemini_error=$(echo "$client_test_results" | jq -r '.gemini_api_key.error' 2>/dev/null)
                    warnings+=("Gemini model test failed: $gemini_error. Check models.gemini in $config_file")
                    gemini_auth='"test_failed"'
                fi
            elif echo "$client_test_results" | jq -e '.gemini_vertex_ai' > /dev/null 2>&1; then
                gemini_success=$(echo "$client_test_results" | jq -r '.gemini_vertex_ai.success' 2>/dev/null)
                if [ "$gemini_success" = "false" ]; then
                    gemini_error=$(echo "$client_test_results" | jq -r '.gemini_vertex_ai.error' 2>/dev/null)
                    warnings+=("Gemini model test failed: $gemini_error. Check models.gemini in $config_file")
                    gemini_auth='"test_failed"'
                fi
            fi

            # Check for OpenAI failures
            if echo "$client_test_results" | jq -e '.openai' > /dev/null 2>&1; then
                openai_success=$(echo "$client_test_results" | jq -r '.openai.success' 2>/dev/null)
                if [ "$openai_success" = "false" ]; then
                    openai_error=$(echo "$client_test_results" | jq -r '.openai.error' 2>/dev/null)
                    warnings+=("OpenAI model test failed: $openai_error. Check models.chatgpt in $config_file")
                    openai_auth="false"
                fi
            fi
        fi
    fi
fi

# Build JSON output
errors_json="[]"
if [ ${#errors[@]} -gt 0 ]; then
    errors_json=$(printf '%s\n' "${errors[@]}" | jq -R . | jq -s .)
fi

warnings_json="[]"
if [ ${#warnings[@]} -gt 0 ]; then
    warnings_json=$(printf '%s\n' "${warnings[@]}" | jq -R . | jq -s .)
fi

# Determine validity: only fatal errors (uv missing, plugin root) make valid=false
# Missing LLM credentials are warnings — the workflow falls back to Opus subagent
valid="true"
exit_code=0
if [ ${#errors[@]} -gt 0 ]; then
    valid="false"
    exit_code=1
fi

# Determine if external LLM review is available
# Both Gemini and OpenAI must be authenticated for full external review
review_available="none"
if [ "$gemini_auth" != "null" ] && [[ "$gemini_auth" != *"no_project"* ]] && [[ "$gemini_auth" != *"no_location"* ]] && [[ "$gemini_auth" != *"stale"* ]] && [[ "$gemini_auth" != *"test_failed"* ]] && [ "$openai_auth" = "true" ]; then
    review_available="full"
elif [ "$gemini_auth" != "null" ] && [[ "$gemini_auth" != *"no_project"* ]] && [[ "$gemini_auth" != *"no_location"* ]] && [[ "$gemini_auth" != *"stale"* ]] && [[ "$gemini_auth" != *"test_failed"* ]]; then
    review_available="gemini_only"
elif [ "$openai_auth" = "true" ]; then
    review_available="openai_only"
fi

echo "{\"valid\": $valid, \"errors\": $errors_json, \"warnings\": $warnings_json, \"gemini_auth\": $gemini_auth, \"openai_auth\": $openai_auth, \"review_available\": \"$review_available\", \"plugin_root\": \"$PLUGIN_ROOT\", \"beads_available\": $beads_available}"
exit $exit_code
