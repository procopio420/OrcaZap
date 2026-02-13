#!/bin/bash
# Lint documentation for sensitive information
# Usage: ./scripts/lint-docs.sh

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track if we found any issues
ISSUES=0

# Patterns to check for
PATTERNS=(
    # IP addresses (but allow 127.0.0.1, localhost, and 10.x.x.x for WireGuard examples)
    '\b(?!127\.0\.0\.1|10\.10\.0\.|localhost)(\d{1,3}\.){3}\d{1,3}\b'
    # Real domains (but allow example.com, localhost, and orcazap.com as examples)
    '\b(?!example\.com|localhost|orcazap\.com)([a-z0-9-]+\.)+[a-z]{2,}\b'
    # Suspicious tokens (long base64-like strings, but allow in code examples)
    '[A-Za-z0-9+/]{40,}={0,2}'
    # Common secret patterns
    '(?i)(password|secret|token|key|api_key|access_token)\s*[:=]\s*[^\s"'\''\`]{20,}'
)

# Files to check (markdown files in docs/ and root, excluding archive)
FILES=$(find . -type f \( -name "*.md" -o -name "*.mdx" \) \
    -not -path "./.git/*" \
    -not -path "./venv/*" \
    -not -path "./docs/archive/*" \
    -not -path "./node_modules/*" \
    -not -path "./.cursor/*")

echo "Checking documentation for sensitive information..."
echo ""

for file in $FILES; do
    # Skip if file doesn't exist
    [ -f "$file" ] || continue
    
    # Check each pattern
    for pattern in "${PATTERNS[@]}"; do
        # Use grep to find matches (case-insensitive, extended regex)
        if grep -qiE "$pattern" "$file" 2>/dev/null; then
            # Check if it's in a code block (```) or inline code (`)
            # This is a simple heuristic - may have false positives
            line_num=0
            in_code_block=false
            while IFS= read -r line; do
                line_num=$((line_num + 1))
                # Toggle code block state
                if [[ "$line" =~ ^\`\`\` ]]; then
                    in_code_block=$((!in_code_block))
                    continue
                fi
                # Skip if in code block
                if [ "$in_code_block" = true ]; then
                    continue
                fi
                # Check for inline code (simple heuristic)
                if [[ "$line" =~ \`.*\` ]]; then
                    # Might be in inline code, but check anyway
                    :
                fi
                # Check if line matches pattern
                if echo "$line" | grep -qiE "$pattern"; then
                    echo -e "${RED}⚠️  Potential issue in $file:${NC}"
                    echo -e "   Line $line_num: ${YELLOW}$line${NC}"
                    echo ""
                    ISSUES=$((ISSUES + 1))
                fi
            done < "$file"
        fi
    done
done

# Check for specific known sensitive patterns
echo "Checking for known sensitive patterns..."
echo ""

# Check for real IPs (excluding localhost and WireGuard examples)
if grep -rE '\b(191\.252\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.)' \
    --include="*.md" \
    --exclude-dir=".git" \
    --exclude-dir="venv" \
    --exclude-dir="docs/archive" \
    --exclude-dir="node_modules" \
    --exclude-dir=".cursor" \
    . 2>/dev/null | grep -v "docs/archive" | grep -v "127.0.0.1" | grep -v "10.10.0."; then
    echo -e "${RED}⚠️  Found potential real IP addresses${NC}"
    ISSUES=$((ISSUES + 1))
fi

# Summary
echo ""
if [ $ISSUES -eq 0 ]; then
    echo -e "${GREEN}✅ No sensitive information found in documentation${NC}"
    exit 0
else
    echo -e "${RED}❌ Found $ISSUES potential issue(s)${NC}"
    echo ""
    echo "Please review the issues above and:"
    echo "  - Remove real IP addresses, domains, tokens, or secrets"
    echo "  - Replace with placeholders or environment variable references"
    echo "  - Move sensitive information to private runbooks"
    exit 1
fi

