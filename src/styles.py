"""CSS styles for the Symbol Quick Wallet application."""

CSS = """
Screen {
    background: #1e1e2e;
}

Header {
    background: #181825;
    text-style: bold;
    padding: 0 1;
    height: 3;
}

#connection-status {
    background: #181825;
    color: #a6adc8;
    padding: 0 2;
    height: 1;
    text-align: right;
    dock: top;
}

Footer {
    background: #181825;
    height: 2;
}

Tabs {
    background: #181825;
    height: 3;
}

Tab {
    background: #1e1e2e;
    text-style: bold;
    padding: 0 1;
    min-height: 1;
}

Tab.active {
    background: #22d3ee;
    color: #0f172a;
    text-style: bold reverse;
}

DataTable {
    background: #1e1e2e;
    border: solid #3b82f6;
}

DataTable.cursor {
    background: #3b82f6;
    color: #ffffff;
    text-style: bold;
}

Button {
    background: transparent;
    color: #3b82f6;
    border: none;
    height: 3;
    min-height: 3;
    min-width: 20;
    padding: 0 1;
    margin: 0;
    content-align: center middle;
}

Button:focus {
    background: #3b82f6;
    color: #ffffff;
    text-style: bold underline reverse;
}

Horizontal {
    height: auto;
    margin: 0 0 1 0;
}

Horizontal > * {
    height: auto;
}

#add-mosaic-button {
    width: 16;
    min-width: 16;
    height: 3;
    min-height: 3;
    border: solid #22c55e;
    color: #22c55e;
    text-style: bold;
}

#remove-mosaic-button {
    width: 16;
    min-width: 16;
    height: 3;
    min-height: 3;
    border: solid #f43f5e;
    color: #f43f5e;
    text-style: bold;
}

#add-mosaic-button:hover {
    background: #22c55e;
    color: #0f172a;
}

#remove-mosaic-button:hover {
    background: #f43f5e;
    color: #0f172a;
}

#mosaics-table {
    width: 1fr;
    min-height: 6;
    margin-top: 1;
    margin-bottom: 1;
}

Button:hover {
    background: #3b82f6;
    color: #ffffff;
    text-style: underline;
}

Button:focus {
    background: #3b82f6;
    color: #ffffff;
    text-style: bold underline reverse;
}

Button.primary {
    background: #22d3ee;
    color: #0f172a;
    border: solid #22d3ee;
    text-style: bold;
}

Button.primary:hover {
    background: #67e8f9;
}

Select {
    background: #181825;
    border: solid #3b82f6;
    min-height: 1;
    padding: 0 1;
}

Select > OptionList {
    background: #181825;
    border: solid #3b82f6;
}

Vertical, Horizontal {
    padding: 0 1;
}

#content {
    padding: 1;
}

#dashboard-tab, #transfer-tab, #address-book-tab, #history-tab {
    padding: 1 2;
}

#transfer-tab Label {
    margin-bottom: 0;
}

#transfer-helper {
    color: #94a3b8;
    margin-bottom: 1;
}

#selected-mosaics-title {
    color: #67e8f9;
    text-style: bold;
    margin-top: 1;
}

#transfer-result {
    min-height: 2;
    margin-top: 1;
    color: #f8fafc;
}

#transfer-tab Horizontal {
    margin-top: 1;
}

#mosaic-actions-row {
    height: 3;
    margin-top: 0;
    margin-bottom: 1;
}

#mosaic-actions-row > Button {
    width: 16;
    min-width: 16;
}

#transfer-actions-row {
    height: 3;
    margin-top: 0;
    margin-bottom: 1;
}

#transfer-actions-row > Button {
    width: 20;
    min-width: 20;
}

#queue-actions-row {
    height: 3;
    margin-top: 0;
    margin-bottom: 1;
}

#queue-actions-row > Button {
    width: 20;
    min-width: 20;
}

#queue-title, #batch-result-title {
    text-style: bold;
    color: #67e8f9;
    margin-bottom: 1;
    border-bottom: solid #22d3ee;
    padding-bottom: 0;
}

#queue-count {
    color: #a6adc8;
    margin-bottom: 1;
}

#total-fee {
    color: #fbbf24;
    margin-top: 1;
    margin-bottom: 1;
}

#batch-summary {
    color: #a6adc8;
    margin-top: 1;
    margin-bottom: 1;
}

#transfer-title, #dashboard-title, #address-book-title, #history-title, #confirm-title, #qr-address {
    text-style: bold;
    color: #67e8f9;
    margin-bottom: 1;
    border-bottom: solid #22d3ee;
    padding-bottom: 0;
}

#wallet-info, #balance-info {
    padding: 0 1;
    background: #181825;
    border: solid #3b82f6;
    margin: 0 0 1 0;
}

Label {
    color: #e2e8f0;
}

Input {
    background: #181825;
    border: solid #3b82f6;
    color: #e2e8f0;
    padding: 0 1;
    min-height: 1;
}

Static {
    color: #a6adc8;
}

.hidden {
    display: none;
}

ModalScreen {
    align: center middle;
}

 ModalScreen > Vertical {
    border: solid #22d3ee;
    border-title-style: bold;
    background: #181825;
    padding: 1 2;
  }

  #tx-hash-display {
    background: #181825;
    border: solid #3b82f6;
    padding: 0 1;
    margin: 0 0 1 0;
    color: #e2e8f0;
  }

  #result-title {
    text-style: bold;
    color: #67e8f9;
    margin-bottom: 1;
    border-bottom: solid #22d3ee;
    padding-bottom: 0;
  }
"""
