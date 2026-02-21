## Fix error handling for network timeouts

- **Status**: completed
- **Priority**: high

The wallet currently doesn't handle network timeouts gracefully. When a node is slow or unresponsive, the UI freezes without clear feedback to the user.
**Improvements needed:**
- Add timeout configuration
- Show loading indicators during network operations
- Display meaningful error messages
- Implement retry logic with exponential backoff
---
---
---
---

---

## Add input validation for transfer amounts

- **Status**: completed
- **Priority**: high

Users can input invalid amounts (negative, too many decimals, etc.) which may cause confusing errors.
**Required:**
- Validate amount format before submission
- Check against mosaic divisibility
- Show inline validation errors
- Prevent submission of invalid data
---
---
---
---

---

## Improve test coverage

- **Status**: completed
- **Priority**: medium

Current test coverage is minimal. Need comprehensive tests for:
- Wallet encryption/decryption
- Transaction building and signing
- Address validation
- Mosaic amount conversion
- Error scenarios
---
---
---
---

---

## Handle offline/online state gracefully

- **Status**: completed
- **Priority**: medium

The app doesn't detect or handle network state changes. Users should be notified when:
- Network is unavailable
- Node connection is lost
- Connection is restored
---
---
---
---

---

## Add transaction confirmation status polling

- **Status**: completed
- **Priority**: medium

After submitting a transaction, the app should poll for confirmation status and update the UI accordingly instead of just showing a loading indicator.
