# Two-Stage Review: Step 4

## Stage 1: Senior Engineer Review

### Issues Found

1. **Margin Calculation is Placeholder**
   - **Issue**: Margin calculation in `calculate_quote_totals()` just uses `margin_min_pct` from rules, not actual calculated margin
   - **Location**: `app/domain/pricing.py:166`
   - **Impact**: Margin percentage is not accurate - should be (total - cost) / total, but we don't have cost basis

2. **Unknown SKUs Not Passed to Approval Check**
   - **Issue**: `unknown_skus` list is collected but not passed to `check_approval_required()` in `generate_quote()`
   - **Location**: `app/domain/quote.py:131-136` - `check_approval_required()` call doesn't include `unknown_skus`
   - **Impact**: Unknown SKUs won't trigger approval requirement

3. **Item Matching Too Permissive**
   - **Issue**: Item matching uses `ilike(f"%{item_name}%")` which can match wrong items
   - **Location**: `app/worker/handlers.py:242`
   - **Impact**: "Cimento" might match "Cimento 50kg" and "Cimento 25kg" - which one is selected?

4. **Transaction Safety in Quote Generation**
   - **Issue**: Quote is created and committed before checking if message send succeeds
   - **Location**: `app/worker/handlers.py:356, 364` - commits before sending quote message
   - **Impact**: If quote message send fails, quote is already committed but not sent

5. **Freight Error Handling Inconsistent**
   - **Issue**: If freight calculation fails, freight is set to 0 and approval required, but this might not be desired behavior
   - **Location**: `app/domain/quote.py:121-127`
   - **Impact**: Freight failures always require approval, even for small amounts

6. **Missing Input Validation in Parsing**
   - **Issue**: `parse_data_capture_message()` doesn't validate extracted data (e.g., quantity > 0, valid CEP format)
   - **Location**: `app/domain/parsing.py`
   - **Impact**: Invalid data might pass through

7. **Quote Status Set Before Send**
   - **Issue**: Quote status set to SENT before actually sending the message
   - **Location**: `app/worker/handlers.py:364`
   - **Impact**: Quote marked as sent even if send fails

8. **No Handling for Multiple Item Matches**
   - **Issue**: If multiple items match a name, only first is used
   - **Location**: `app/worker/handlers.py:240-244`
   - **Impact**: Wrong item might be selected

9. **Missing Structured Logging in Domain Functions**
   - **Issue**: Domain functions (pricing, freight, quote) don't include structured logging with request_id
   - **Location**: `app/domain/pricing.py`, `app/domain/freight.py`, `app/domain/quote.py`
   - **Impact**: Harder to trace issues (R5 requirement)

## Stage 2: Junior Engineer Suggestions (Based on Senior Review)

### Critical Fixes (Must Apply)

1. **Pass unknown_skus to approval check**: Fix missing parameter
2. **Fix transaction safety**: Don't commit quote before message send succeeds
3. **Fix quote status**: Only set to SENT after successful send
4. **Add structured logging**: Include request_id/provider_message_id in domain functions

### Important Improvements (Should Apply)

5. **Improve item matching**: Use exact match first, then fuzzy, handle multiple matches
6. **Add input validation**: Validate parsed data (quantities, CEP format)
7. **Document margin calculation**: Add comment explaining it's simplified for MVP

### Nice-to-Have (Consider)

8. **Improve freight error handling**: Maybe allow configurable behavior
9. **Handle multiple item matches**: Return best match or ask for clarification
10. **Calculate actual margin**: Would require cost basis data (future enhancement)

## Stage 3: Second Senior Review (Critical Evaluation)

### Validated Suggestions (Apply These)

1. ✅ **Pass unknown_skus to approval check**: Critical - approval logic incomplete
2. ✅ **Fix transaction safety**: Critical - prevents data inconsistency
3. ✅ **Fix quote status**: Important - status should reflect reality
4. ✅ **Add structured logging**: Required by R5 - traceability
5. ✅ **Improve item matching**: Important - prevents wrong item selection
6. ✅ **Add input validation**: Important - prevents invalid data
7. ✅ **Document margin calculation**: Simple - improves code clarity

### Rejected Suggestions (Don't Apply)

8. ❌ **Improve freight error handling**: Current behavior is acceptable for MVP - freight failure requiring approval is reasonable
9. ❌ **Handle multiple item matches**: Over-engineering for MVP - first match is fine, can improve later
10. ❌ **Calculate actual margin**: Would require cost basis which is out of scope for MVP

## Action Items

Apply validated suggestions 1-7.


