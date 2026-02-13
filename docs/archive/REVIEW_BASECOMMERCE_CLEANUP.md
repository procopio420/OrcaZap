# Review: BaseCommerce Cleanup Scripts

## Overview

This review covers the implementation of scripts to remove BaseCommerce and optionally Docker from VPS hosts.

## Files Created

1. `infra/scripts/ops/remove_basecommerce.sh` - Removes BaseCommerce containers, images, volumes, networks, and directories
2. `infra/scripts/ops/remove_docker.sh` - Completely removes Docker from the host
3. `infra/scripts/ops/verify_clean_host.sh` - Verifies the host is clean of BaseCommerce artifacts
4. Updated `infra/README.md` with comprehensive documentation

## Senior Review (R1)

### Strengths

1. **Idempotency**: All scripts are idempotent and can be run multiple times safely
2. **Safety**: Explicit confirmation environment variables required (`CONFIRM_REMOVE_BASECOMMERCE=1`, `CONFIRM_REMOVE_DOCKER=1`)
3. **Dry-run support**: All scripts support `--dry-run` mode for safe testing
4. **Error handling**: Proper use of `set -euo pipefail` and error checking
5. **Logging**: Clear, structured logging using common.sh functions
6. **Documentation**: Comprehensive README updates with examples

### Issues Found

1. **Missing inventory loading**: The scripts don't load inventory variables, so `VPS1_SSH_USER` and `VPS1_SSH_PORT` may not be available
2. **Hardcoded user assumption**: Scripts assume `VPS1_SSH_USER` but should work for any host
3. **Docker command availability**: The `check_docker_installed` function may fail if Docker is installed but not in PATH
4. **Volume removal safety**: Docker volumes may be in use by other containers; should check before removal
5. **Compose file detection**: The compose file search may miss files if they're in non-standard locations

### Recommendations

1. Add inventory loading to scripts that need it
2. Make user/port detection more robust (use inventory or defaults)
3. Improve Docker detection to check for service status, not just command
4. Add warnings for volume removal if other containers exist
5. Expand compose file search to include more common locations

## Junior Engineer Suggestions (R2)

### Minor Improvements

1. **Better error messages**: Add more context to error messages (e.g., which container failed to remove)
2. **Progress indicators**: For long operations, show progress (e.g., "Removing 3 containers...")
3. **Backup option**: Optionally create backups before removal (for safety)
4. **Logging to file**: Option to log operations to a file for audit trail
5. **Parallel operations**: For multiple containers/images, remove in parallel for speed

### Code Quality

1. **Function documentation**: Add brief comments explaining what each function does
2. **Variable validation**: Validate that required environment variables are set early
3. **Exit codes**: Use consistent exit codes (0=success, 1=error, 2=usage error)
4. **Test coverage**: Add basic integration tests for dry-run mode

## Second Senior Review (R3)

### Validation of Junior Suggestions

**Accepted:**
- Better error messages (high value, low risk)
- Function documentation (improves maintainability)
- Variable validation (safety improvement)

**Deferred:**
- Progress indicators (nice-to-have, adds complexity)
- Backup option (adds complexity, may not be needed)
- Logging to file (can be added later if needed)
- Parallel operations (premature optimization)
- Test coverage (can be added incrementally)

### Critical Issues to Address

1. **Inventory loading**: Must be fixed - scripts won't work without it
2. **Docker detection**: Should check service status, not just command existence
3. **User/port handling**: Should work for any host, not just VPS1

## Changes to Apply

1. Add inventory loading to all three scripts
2. Improve Docker detection to check service status
3. Make user/port detection more flexible
4. Add function documentation comments
5. Improve error messages with context
6. Add early validation of environment variables


