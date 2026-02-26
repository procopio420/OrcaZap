#!/bin/bash
# Purge sensitive data from Git history
# WARNING: This rewrites Git history. Use with caution.
#
# Usage:
#   ./scripts/purge-git-history.sh
#
# This script uses git-filter-repo (preferred) or git filter-branch to:
# 1. Remove sensitive files from all commits
# 2. Replace sensitive patterns in file history
# 3. Clean up Git history

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "⚠️  WARNING: This script will rewrite Git history"
echo "   This is a destructive operation!"
echo ""
echo "Before proceeding:"
echo "  1. Make a backup: git clone --mirror <repo-url> backup.git"
echo "  2. Ensure you have git-filter-repo installed: pip install git-filter-repo"
echo "  3. Ensure you're on a clean working directory"
echo ""
read -p "Continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    exit 1
fi

# Check if git-filter-repo is available
if command -v git-filter-repo &> /dev/null; then
    echo "✅ Using git-filter-repo"
    USE_FILTER_REPO=true
else
    echo "⚠️  git-filter-repo not found. Using git filter-branch (slower)"
    echo "   Install git-filter-repo: pip install git-filter-repo"
    USE_FILTER_REPO=false
fi

# Files to remove from history
SENSITIVE_FILES=(
    "infra/deploy_key"
    "infra/deploy_key.pub"
    "infra/origin.key"
    "infra/origin.pem"
    "infra/inventory/hosts.env"
    "infra/scripts/setup/wireguard-keys.env"
    ".env"
    "*.env"
    "*.key"
    "*.pem"
)

# Patterns to replace (old -> new)
declare -A PATTERNS=(
    ["191.252.120.36"]="<VPS1_HOST>"
    ["191.252.120.182"]="<VPS2_HOST>"
    ["191.252.120.176"]="<VPS3_HOST>"
    ["_uetYjvZLNd6uAlJQZO1km_Lzl8EmpBeOCuTzpvEgEI"]="<POSTGRES_PASSWORD>"
    ["W3oXTVOmlK3X7UXJ6aslgcwSO2Bh6VPnSfYCH3rmmcI"]="<REDIS_PASSWORD>"
    ["IDwl/sRLRUV/AT2Y041av/p9AzhlsnmP5k0WMLrAjUQ="]="<VPS1_WIREGUARD_PRIVATE_KEY>"
    ["EBy4P6HYL2rXohKmLUcIVB51WHjhRKpwbSr1ecKaHVE="]="<VPS2_WIREGUARD_PRIVATE_KEY>"
    ["EHAkAOtMV0AE7CUBH5Pnr4JxgweV0Pk2d7+gcYVF/mw="]="<VPS3_WIREGUARD_PRIVATE_KEY>"
)

if [ "$USE_FILTER_REPO" = true ]; then
    # Remove sensitive files
    echo "Removing sensitive files from history..."
    for file in "${SENSITIVE_FILES[@]}"; do
        git-filter-repo --path "$file" --invert-paths --force
    done

    # Replace sensitive patterns
    echo "Replacing sensitive patterns in history..."
    for pattern in "${!PATTERNS[@]}"; do
        replacement="${PATTERNS[$pattern]}"
        git-filter-repo --replace-text <(echo "$pattern==>$replacement") --force
    done

    echo "✅ History cleaned with git-filter-repo"
else
    echo "⚠️  Using git filter-branch (this may take a while)..."
    
    # Remove sensitive files
    git filter-branch --force --index-filter \
        "git rm --cached --ignore-unmatch ${SENSITIVE_FILES[*]}" \
        --prune-empty --tag-name-filter cat -- --all

    # Replace patterns
    for pattern in "${!PATTERNS[@]}"; do
        replacement="${PATTERNS[$pattern]}"
        git filter-branch --force --tree-filter \
            "find . -type f -exec sed -i 's|$pattern|$replacement|g' {} +" \
            --prune-empty --tag-name-filter cat -- --all
    done

    # Clean up
    git for-each-ref --format="%(refname)" refs/original/ | xargs -n 1 git update-ref -d
    git reflog expire --expire=now --all
    git gc --prune=now --aggressive

    echo "✅ History cleaned with git filter-branch"
fi

echo ""
echo "⚠️  IMPORTANT NEXT STEPS:"
echo "  1. Review the changes: git log --all"
echo "  2. If repository was pushed to remote, force-push:"
echo "     git push --force --all"
echo "     git push --force --tags"
echo "  3. Notify all collaborators (they'll need to re-clone)"
echo "  4. Rotate all exposed credentials immediately"
echo ""
echo "✅ Git history cleanup complete"




