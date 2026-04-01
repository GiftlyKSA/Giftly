# Coding Style Guide (Language-Agnostic)

## Naming Conventions

### General
- Use English only for identifiers.
- Use descriptive names; avoid abbreviations.
- Names must reflect intent, not implementation.

### Variables
- Use snake_case.
- Must be nouns.

Examples:
user
order_list
total_price

---

### Functions / Methods
- Use snake_case.
- Must be verbs or verb phrases.

Examples:
create_user
fetch_orders
calculate_total

---

### Booleans
- Must be prefixed with:
  - is_
  - has_
  - should_
  - can_

Examples:
is_active
has_permission
should_retry

---

### Constants
- Use UPPER_CASE.
- Use underscore as separator.

Examples:
MAX_RETRIES
DEFAULT_TIMEOUT
API_BASE_URL

---

### Classes / Types
- Use PascalCase.

Examples:
UserService
OrderManager
PaymentProcessor

---

### Files
- Use snake_case.

Examples:
user_service
payment_handler
api_client

---

### Modules / Folders
- Use snake_case.
- Represent a domain or feature.

Examples:
auth/
billing/
notifications/

---

## Function Rules
- Max length: 30 lines
- Max parameters: 4
- Must have single responsibility
- Max nesting depth: 3 levels

---

## Control Flow

- Prefer early returns over nested conditions.

Example:
if not valid:
    return error

process()

---

- Avoid complex inline conditions.

Bad:
if a and b and not c and (d or e):

Good:
is_valid = a and b and not c
has_access = d or e

if is_valid and has_access:
    proceed()

---

## Data & State
- Avoid global mutable state.
- Prefer immutable data where possible.
- Pass dependencies explicitly.

---

## Error Handling
- Do not swallow errors silently.
- Errors must be:
  - logged OR
  - returned OR
  - re-thrown

---

## Comments
- Do not explain obvious code.
- Only explain:
  - why
  - edge cases
  - non-obvious decisions

---

## Magic Values
- No magic numbers or strings inline.

Bad:
if retries > 3:

Good:
if retries > MAX_RETRIES:

---

## Imports / Dependencies
- No unused imports.
- Group imports:
  1. standard
  2. third-party
  3. local

---

## Testing
- Code must be testable in isolation.
- Avoid hard dependencies; use injection.

---

## Code Cleanliness
- No dead code.
- No commented-out blocks.
- No debug logs in production.

---

## Disallowed Patterns
- Multiple responsibilities in one function
- Deep nesting (>3 levels)
- Hidden side effects
- Hardcoded credentials
- Circular dependencies

---

## Defaults
- Indentation: 4 spaces
- Max line length: 100 characters
- Encoding: UTF-8

---

## Priority Order
1. Readability
2. Consistency
3. Simplicity
4. Performance