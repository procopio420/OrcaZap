# Two-Stage Review: Infrastructure Automation (INF0-INF4)

## Stage 1: Senior Engineer Review

### Issues Found

1. **Inconsistent Argument Parsing**
   - **Issue**: `parse_args()` in `common.sh` doesn't handle all scripts' custom arguments (e.g., `--branch`, `--clean`, `--workers`)
   - **Location**: `infra/scripts/lib/common.sh:50-70` - `parse_args()` only handles common args
   - **Impact**: Scripts parse arguments twice (once in `parse_args()`, once in `main()`), causing confusion

2. **TARGET_HOST Not Set by parse_args**
   - **Issue**: `parse_args()` doesn't set `TARGET_HOST` variable, scripts check it later
   - **Location**: Multiple scripts check `if [ -z "${TARGET_HOST:-}" ]` after `parse_args()`
   - **Impact**: Inconsistent behavior - `--host` flag parsed but variable not set

3. **Missing Error Handling in Template Rendering**
   - **Issue**: Template rendering uses `sed` which can fail silently if template file missing
   - **Location**: `infra/scripts/bootstrap/10_wireguard.sh:96-99`, similar in other scripts
   - **Impact**: Scripts may continue with empty/broken configs

4. **SSH Key Handling Inconsistent**
   - **Issue**: Some scripts use `SSH_PRIVATE_KEY` env var, others rely on SSH agent
   - **Location**: `infra/scripts/lib/ssh.sh` - `ssh_exec()` checks for key but not all scripts set it
   - **Impact**: Scripts may fail if SSH key not in agent

5. **Terraform Inventory Parsing Fragile**
   - **Issue**: Terraform parses inventory file with simple string splitting, no validation
   - **Location**: `infra/terraform/main.tf:4-8` - splits on `=` without handling quoted values
   - **Impact**: Inventory values with `=` in them will break parsing

6. **Missing Validation in Deploy Scripts**
   - **Issue**: Deploy scripts don't validate git repo exists before trying to pull
   - **Location**: `infra/scripts/deploy/deploy_app.sh:44-53` - checks `.git` but doesn't validate repo URL
   - **Impact**: May fail with unclear error if repo not cloned

7. **Health Check Too Permissive**
   - **Issue**: Health check accepts any non-empty response, not just valid JSON
   - **Location**: `infra/scripts/deploy/healthcheck.sh:62` - grep for "ok|healthy|alive|status" or any response
   - **Impact**: May pass health check even if app is returning errors

8. **No Rollback Mechanism in Deploy**
   - **Issue**: If deployment fails after code pull but before service restart, no rollback
   - **Location**: `infra/scripts/deploy/deploy_app.sh` - no git reset on failure
   - **Impact**: Partial deployments leave system in inconsistent state

9. **Cleanup Scripts Don't Handle Running Services**
   - **Issue**: Cleanup scripts stop services but don't wait for graceful shutdown
   - **Location**: `infra/scripts/cleanup/cleanup_app.sh:213` - `systemctl stop` without timeout
   - **Impact**: May kill services abruptly, losing in-flight requests

10. **Missing Input Sanitization**
    - **Issue**: Scripts don't sanitize user input (hostnames, paths) before using in commands
    - **Location**: Multiple scripts use `$TARGET_HOST` directly in SSH commands
    - **Impact**: Command injection vulnerability if hostname contains special characters

11. **Terraform fileexists() Function Usage**
    - **Issue**: `fileexists()` is not a standard Terraform function - should use `file()` with try/catch
    - **Location**: `infra/terraform/main.tf:3` - uses `fileexists()` which doesn't exist
    - **Impact**: Terraform will fail to validate

12. **No Connection Retry Logic**
    - **Issue**: SSH connections fail immediately, no retry for transient network issues
    - **Location**: `infra/scripts/lib/ssh.sh` - `ssh_exec()` has no retry logic
    - **Impact**: Deployment may fail due to temporary network issues

## Stage 2: Junior Engineer Suggestions (Based on Senior Review)

### Critical Fixes (Must Apply)

1. **Fix Terraform fileexists()**: Use proper Terraform syntax with try() function
2. **Fix TARGET_HOST parsing**: Make `parse_args()` set `TARGET_HOST` variable
3. **Add template validation**: Check template file exists before rendering
4. **Improve health check**: Validate JSON response, check status code
5. **Add input sanitization**: Sanitize hostnames and paths before use

### Important Improvements (Should Apply)

6. **Add rollback mechanism**: Git reset on deployment failure
7. **Improve error handling**: Better error messages, validation
8. **Add connection retry**: Retry SSH connections on failure
9. **Graceful service shutdown**: Wait for services to stop gracefully
10. **Consolidate argument parsing**: Make `parse_args()` handle all common args

### Nice-to-Have (Consider)

11. **Add deployment verification**: Check service is actually running after restart
12. **Add connection pooling**: Reuse SSH connections
13. **Add progress indicators**: Show progress for long operations
14. **Add deployment history**: Log deployments for audit

## Stage 3: Second Senior Review (Critical Evaluation)

### Validated Suggestions (Apply These)

1. ✅ **Fix Terraform fileexists()**: Critical - Terraform won't work without this
2. ✅ **Fix TARGET_HOST parsing**: Important - inconsistent behavior
3. ✅ **Add template validation**: Important - prevents broken configs
4. ✅ **Improve health check**: Important - better validation
5. ✅ **Add input sanitization**: Critical - security issue
6. ✅ **Add rollback mechanism**: Important - prevents inconsistent state
7. ✅ **Improve error handling**: Important - better debugging
8. ✅ **Add connection retry**: Nice but not critical for MVP
9. ✅ **Graceful service shutdown**: Important - prevents data loss
10. ✅ **Consolidate argument parsing**: Important - code quality

### Rejected Suggestions (Don't Apply)

11. ❌ **Add deployment verification**: Over-engineering - health check already does this
12. ❌ **Add connection pooling**: Over-engineering for MVP - scripts are short-lived
13. ❌ **Add progress indicators**: Nice-to-have, not critical
14. ❌ **Add deployment history**: Can add later, not critical for MVP

## Action Items

Apply validated suggestions 1-10.


