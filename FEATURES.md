## Add multi-account support

- **Status**: completed
- **Priority**: high

Allow users to manage multiple accounts/wallets within the same application.
**Features:**
- Create/import multiple wallets
- Quick switch between accounts
- Separate address books per account or shared
- Account labels/nicknames
---
---
---

---

## Implement transaction queue

- **Status**: completed
- **Priority**: medium

Allow users to prepare multiple transactions and batch submit them.
**Benefits:**
- Better UX for multiple transfers
- Reduce network calls
- Aggregate fees display
---
---
---

---

## Add address QR code scanner

- **Status**: completed
- **Priority**: medium

Allow users to scan QR codes to import addresses for transfers.
**Implementation:**
- Integrate camera access
- Parse Symbol QR code format
- Support both address and transaction QR codes
---
---
---

---

## Add mosaic metadata viewer

- **Status**: completed
- **Priority**: low

Display mosaic metadata and properties when viewing balances.
**Information to show:**
- Mosaic name (if available)
- Divisibility
- Supply
- Owner address
- Description
---
---
---

---

## Implement contact groups

- **Status**: completed
- **Priority**: low

Organize address book contacts into groups for easier management.
**Features:**
- Create/edit/delete groups
- Assign contacts to groups
- Filter by group in transfer screen
---
---
---

---

## Add transaction templates

- **Status**: completed
- **Priority**: low

Save frequently used transfer configurations as templates.
**Use cases:**
- Recurring payments
- Common transfer patterns
- Quick access to frequent recipients

---

## Feature-based module organization

- **Status**: pending
- **Priority**: high

Reorganize the codebase into feature-based modules for better maintainability and testability.
**Target Structure:**
```
src/
  features/
    transfer/           # Transfer feature (service.py, screen.py, validators.py)
    address_book/       # Address book feature
    mosaic/             # Mosaic management feature
  shared/               # Shared utilities (network, validation, clipboard)
```
**Tasks:**
- [ ] Create `src/features/` directory structure
- [ ] Migrate transfer functionality to `src/features/transfer/`
- [ ] Migrate address book to `src/features/address_book/`
- [ ] Migrate mosaic management to `src/features/mosaic/`
- [ ] Move shared utilities to `src/shared/`
- [ ] Update tests to mirror feature structure (`tests/features/`)
- [ ] Update imports throughout codebase
- [ ] Verify all tests pass after migration

---

## Add namespace support

- **Status**: pending
- **Priority**: medium

Allow users to register and manage namespaces for their accounts and mosaics.
**Features:**
- Register new namespaces (root and sub-namespaces)
- Link namespaces to addresses and mosaics
- View namespace ownership and expiration
- Send transactions using friendly names (e.g., `xembook.xym`)
**Implementation:**
- Reference `docs/quick_learning_symbol_v3/06_namespace.md`

---

## Implement aggregate transactions

- **Status**: pending
- **Priority**: medium

Support aggregate bonded and complete transactions for multi-party workflows.
**Features:**
- Create aggregate transactions with multiple inner transactions
- Support partial transactions requiring cosignatures
- Display pending cosignature requests
- Sign aggregate transactions from other initiators
**Implementation:**
- Reference `docs/quick_learning_symbol_v3/04_transaction.md#46-アグリゲートトランザクション`

---

## Add multisig account support

- **Status**: pending
- **Priority**: medium

Allow users to configure and use multisignature accounts.
**Features:**
- Convert accounts to multisig
- Add/remove cosignatories
- Set approval and removal thresholds
- Initiate and sign multisig transactions
**Implementation:**
- Reference `docs/quick_learning_symbol_v3/09_multisig.md`

---

## Add real-time transaction monitoring

- **Status**: pending
- **Priority**: low

Implement WebSocket-based real-time monitoring for incoming transactions.
**Features:**
- Listen for incoming transactions to watched addresses
- Notify on block finalization
- Monitor cosignature requests
- Background transaction status updates
**Implementation:**
- Reference `docs/quick_learning_symbol_v3/10_observer.md`

---

## Add metadata registration

- **Status**: pending
**Priority**: low

Allow users to attach metadata to accounts, mosaics, and namespaces.
**Features:**
- Assign key-value metadata to own account
- Attach metadata to owned mosaics
- Attach metadata to owned namespaces
- View and edit existing metadata
**Implementation:**
- Reference `docs/quick_learning_symbol_v3/07_metadata.md`

---

## Implement hash lock and secret lock

- **Status**: pending
- **Priority**: low

Add support for lock transactions for cross-chain swaps and conditional payments.
**Features:**
- Create hash lock transactions for aggregate bonded
- Create secret lock/proof for atomic swaps
- View and claim locked funds
- Support cross-chain exchange workflows
**Implementation:**
- Reference `docs/quick_learning_symbol_v3/08_lock.md`
