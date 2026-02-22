## Add multi-account support

- **Status**: completed
- **Priority**: high

Allow users to manage multiple accounts/wallets within the same application.
**Features:**
- Create/import multiple wallets
- Quick switch between accounts
- Separate address books per account or shared
- Account labels/nicknames
### Self-Check (Production Logic)
- [ ] Create a new account and verify it appears in account list
- [ ] Switch between accounts and verify correct address is displayed
- [ ] Import account via private key and verify correct address derived
- [ ] Delete account (when multiple exist) and verify removal
- [ ] Verify address book sharing setting works per account
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
### Self-Check (Production Logic)
- [ ] Add transaction to queue and verify it persists after app restart
- [ ] Remove transaction from queue and verify removal
- [ ] Clear queue and verify all transactions removed
- [ ] Verify estimated fee calculation for queued transactions
- [ ] Reorder transactions and verify new order persists
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
### Self-Check (Production Logic)
- [ ] Parse raw Symbol address from string (e.g., "TABC123...")
- [ ] Parse JSON QR with address and mosaics
- [ ] Parse Symbol official QR payload format (v/data base64)
- [ ] Verify invalid QR returns appropriate error
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
### Self-Check (Production Logic)
- [ ] Fetch mosaic info from node and verify divisibility is correct
- [ ] Verify mosaic name resolution (XYM should show "XYM")
- [ ] Verify owner address matches expected
- [ ] Format mosaic amount correctly based on divisibility
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
### Self-Check (Production Logic)
- [ ] Create contact group and verify it appears in group list
- [ ] Add contact to group and verify association
- [ ] Update group name/color and verify persistence
- [ ] Delete group and verify contacts are unassigned (not deleted)
- [ ] Filter addresses by group and verify correct results
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
### Self-Check (Production Logic)
- [ ] Create template and verify it persists after app restart
- [ ] Update template and verify changes saved
- [ ] Delete template and verify removal
- [ ] Load template and verify all fields populated correctly
---

---

## Feature-based module organization

- **Status**: completed
- **Priority**: high

Reorganize the codebase into feature-based modules for better maintainability and testability.
**Structure:**
```
src/
  features/
    transfer/           # Transfer feature (service.py, screen.py, validators.py, handlers.py)
    address_book/       # Address book feature (service.py, screen.py, handlers.py)
    mosaic/             # Mosaic management feature (service.py, screen.py)
    account/            # Account management feature (service.py, handlers.py)
    aggregate/          # Aggregate transactions feature (service.py, screen.py)
  shared/               # Shared utilities (network, validation, clipboard, qr_scanner, etc.)
  screens.py            # General modal screens
  wallet.py             # Core wallet functionality
  transaction.py        # Transaction management
```
**Tests:**
```
tests/
  features/
    transfer/           # Transfer feature tests
    address_book/       # Address book tests
    mosaic/             # Mosaic tests
    account/            # Account management tests
    aggregate/          # Aggregate transaction tests
  shared/               # Shared utility tests (validation, network, clipboard, etc.)
```
---

---

## Add namespace support

- **Status**: completed
- **Priority**: medium

Allow users to register and manage namespaces for their accounts and mosaics.
**Features:**
- Register new namespaces (root and sub-namespaces)
- Link namespaces to addresses and mosaics
- View namespace ownership and expiration
- Send transactions using friendly names (e.g., `xembook.xym`)
**Implementation:**
- Reference `docs/quick_learning_symbol_v3/06_namespace.md`
- Implemented in `src/features/namespace/`
- UI accessible via `/namespaces` command
### Self-Check (Production Logic)
- [x] Resolve namespace to address via node API
- [x] Resolve namespace to mosaic ID via node API
- [x] Verify namespace expiration calculation
- [x] Register root namespace on testnet and verify confirmation
---

---

## Implement aggregate transactions

- **Status**: in_progress
- **Priority**: medium

Support aggregate bonded and complete transactions for multi-party workflows.
**Features:**
- Create aggregate transactions with multiple inner transactions
- Support partial transactions requiring cosignatures
- Display pending cosignature requests
- Sign aggregate transactions from other initiators
**Implementation:**
- Reference `docs/quick_learning_symbol_v3/04_transaction.md#46-アグリゲートトランザクション`
**Current Progress:**
- [x] AggregateService with complete/bonded creation
- [x] Hash lock transaction support
- [x] Cosignature creation and attachment
- [x] Partial transaction fetching and parsing
- [x] Transaction status polling
- [ ] UI screens for aggregate workflow
- [ ] Integration tests on testnet
### Self-Check (Production Logic)
- [ ] Create aggregate complete with inner transfer and announce to testnet
- [ ] Create hash lock transaction and verify lock confirmation
- [ ] Create aggregate bonded after hash lock confirmation
- [ ] Fetch partial transactions from testnet
- [ ] Cosign a partial transaction and verify announcement
- [ ] Poll transaction status until confirmed/failed
---

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
### Self-Check (Production Logic)
- [ ] Convert account to 1-of-2 multisig on testnet
- [ ] Initiate transaction from multisig account
- [ ] Cosign multisig transaction from cosigner
- [ ] Verify multisig account info reflects correct thresholds
---

---

## Add real-time transaction monitoring

- **Status**: completed
- **Priority**: low

Implement WebSocket-based real-time monitoring for incoming transactions.
**Features:**
- Listen for incoming transactions to watched addresses
- Notify on block finalization
- Monitor cosignature requests
- Background transaction status updates
**Implementation:**
- Reference `docs/quick_learning_symbol_v3/10_observer.md`
- Implemented in `src/features/monitoring/service.py`
- Integrated with main app in `src/__main__.py`
### Self-Check (Production Logic)
- [x] Connect to WebSocket endpoint
- [x] Subscribe to address and receive confirmed transactions
- [x] Subscribe to block finalization
- [ ] Receive real-time notification for incoming transfer (requires live test)
---

---

## Add metadata registration

- **Status**: completed
- **Priority**: medium

Allow users to attach metadata to accounts, mosaics, and namespaces.
**Features:**
- Assign key-value metadata to own account
- Attach metadata to owned mosaics
- Attach metadata to owned namespaces
- View and edit existing metadata
**Implementation:**
- Reference `docs/quick_learning_symbol_v3/07_metadata.md`
- Implemented in `src/features/metadata/`
- UI accessible via `/metadata` command
### Self-Check (Production Logic)
- [x] Generate metadata key using SHA3-256 hash
- [x] Create aggregate complete transaction with embedded metadata
- [x] Calculate value delta for updates (XOR encoding)
- [x] Fetch existing metadata from node API
---

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
### Self-Check (Production Logic)
- [ ] Create secret lock with random secret
- [ ] Claim secret lock with proof
- [ ] Create hash lock for aggregate bonded
- [ ] Verify lock refund after expiration
