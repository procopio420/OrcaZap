#!/bin/bash
# Master cleanup script - orchestrates cleanup for all VPS
# Usage: ./cleanup_all.sh [OPTIONS]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB_DIR="$SCRIPT_DIR/../lib"

# Source library functions
source "$LIB_DIR/common.sh"
source "$LIB_DIR/ssh.sh"
source "$LIB_DIR/assert.sh"

# Parse arguments
DRY_RUN=false
CLEAN_APP=false
CLEAN_WORKER=false
CLEAN_DATA=false
CLEAN_ALL=false

show_help() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Orchestrates cleanup for all VPS servers.

Options:
    --dry-run           Show what would be done without making changes
    --clean-app         Clean VPS1 (APP server)
    --clean-worker      Clean VPS3 (WORKER server)
    --clean-data        Clean VPS2 (DATA server) - preserves DB/Redis
    --clean-all         Clean all servers
    --host HOST         Target specific host (overrides --clean-all)
    --help, -h          Show this help message

Examples:
    # Clean all servers
    ./cleanup_all.sh --clean-all

    # Clean only app server
    ./cleanup_all.sh --clean-app

    # Dry-run for app server
    ./cleanup_all.sh --clean-app --dry-run

EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --clean-app)
                CLEAN_APP=true
                shift
                ;;
            --clean-worker)
                CLEAN_WORKER=true
                shift
                ;;
            --clean-data)
                CLEAN_DATA=true
                shift
                ;;
            --clean-all)
                CLEAN_ALL=true
                shift
                ;;
            --host)
                TARGET_HOST="$2"
                shift 2
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

main() {
    init_script "$@"
    load_inventory
    
    if [ "${CLEAN_ALL:-false}" = true ]; then
        CLEAN_APP=true
        CLEAN_WORKER=true
        CLEAN_DATA=true
    fi
    
    if [ -z "${CLEAN_APP:-false}" ] && [ -z "${CLEAN_WORKER:-false}" ] && [ -z "${CLEAN_DATA:-false}" ] && [ -z "${TARGET_HOST:-}" ]; then
        log_error "No cleanup target specified. Use --clean-app, --clean-worker, --clean-data, or --clean-all"
        show_help
        exit 1
    fi
    
    if [ -n "${TARGET_HOST:-}" ]; then
        # Determine which cleanup script to run based on host
        if [ "$TARGET_HOST" = "$VPS1_HOST" ]; then
            log_info "Cleaning VPS1 (APP): $TARGET_HOST"
            "$SCRIPT_DIR/cleanup_app.sh" --host "$TARGET_HOST" ${DRY_RUN:+--dry-run}
        elif [ "$TARGET_HOST" = "$VPS3_HOST" ]; then
            log_info "Cleaning VPS3 (WORKER): $TARGET_HOST"
            "$SCRIPT_DIR/cleanup_worker.sh" --host "$TARGET_HOST" ${DRY_RUN:+--dry-run}
        elif [ "$TARGET_HOST" = "$VPS2_HOST" ]; then
            log_info "Cleaning VPS2 (DATA): $TARGET_HOST"
            "$SCRIPT_DIR/cleanup_data.sh" --host "$TARGET_HOST" ${DRY_RUN:+--dry-run}
        else
            log_error "Unknown host: $TARGET_HOST"
            exit 1
        fi
    else
        if [ "${CLEAN_APP:-false}" = true ]; then
            log_info "Cleaning VPS1 (APP): $VPS1_HOST"
            "$SCRIPT_DIR/cleanup_app.sh" --host "$VPS1_HOST" ${DRY_RUN:+--dry-run}
        fi
        
        if [ "${CLEAN_WORKER:-false}" = true ]; then
            log_info "Cleaning VPS3 (WORKER): $VPS3_HOST"
            "$SCRIPT_DIR/cleanup_worker.sh" --host "$VPS3_HOST" ${DRY_RUN:+--dry-run}
        fi
        
        if [ "${CLEAN_DATA:-false}" = true ]; then
            log_info "Cleaning VPS2 (DATA): $VPS2_HOST"
            "$SCRIPT_DIR/cleanup_data.sh" --host "$VPS2_HOST" ${DRY_RUN:+--dry-run}
        fi
    fi
    
    log_success "Cleanup completed"
}

main "$@"


