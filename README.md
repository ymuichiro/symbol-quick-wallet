# Symbol Quick Wallet

[![PyPI](https://img.shields.io/pypi/v/symbol-quick-wallet)](https://pypi.org/project/symbol-quick-wallet/)
[![Python](https://img.shields.io/pypi/pyversions/symbol-quick-wallet)](https://pypi.org/project/symbol-quick-wallet/)
[![License](https://img.shields.io/pypi/l/symbol-quick-wallet)](https://pypi.org/project/symbol-quick-wallet/)

A simple and secure TUI-based cryptocurrency wallet for the Symbol blockchain (NIS1/Symbol network).

[日本語版](#日本語)

## Concept

Symbol Quick Wallet is designed to provide a minimal, secure, and user-friendly wallet experience for the Symbol blockchain. The key concepts are:

- **Simplicity**: Clean TUI interface with keyboard shortcuts for power users
- **Security**: Local private key storage with encryption options
- **Privacy**: No external services, direct interaction with Symbol nodes
- **Accessibility**: Works in terminal environments, perfect for remote SSH access
- **Cross-Platform**: Runs on macOS, Linux, and Windows

## Features

- ✨ **First-Run Setup**: Easy network selection (testnet/mainnet) and wallet creation/import
- 💰 **Transfer Transactions**: Send XYM and other mosaics with custom messages
- 📒 **Address Book**: Manage your contacts with easy sending
- 🔐 **Wallet Management**: Create new wallets or import existing ones via private key
- 📊 **Balance Tracking**: Real-time balance updates from the network
- 📜 **Transaction History**: View your past transactions with details
- 🔑 **Private Key Export**: Export encrypted private keys with password protection
- 📱 **QR Code Display**: Share your wallet address easily
- 🌐 **Network Switching**: Toggle between testnet and mainnet
- 🎨 **Modern UI**: Catppuccin-inspired dark theme with visual feedback

## Installation

### via pip (Recommended)

```bash
pip install symbol-quick-wallet
```

### via uv (Faster)

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install the package
uv pip install symbol-quick-wallet
```

### From Source

```bash
git clone https://github.com/yourusername/symbol-quick-wallet.git
cd symbol-quick-wallet
uv sync
```

## Quick Start

### First Run

```bash
symbol-quick-wallet
```

On first launch, you will see:
1. **Network Selection**: Choose between Testnet or Mainnet
2. **Wallet Setup**: Create a new wallet or import an existing one

### Using the Wallet

After setup, the main interface appears with tabs:

- **Dashboard**: View your address, balance, and network status
- **Transfer**: Send XYM and mosaics to other addresses
- **Address Book**: Manage your contacts
- **History**: View transaction history
- **Settings**: Configure nodes, manage wallet, and export keys

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `q` | Quit |
| `d` | Dashboard |
| `t` | Transfer |
| `a` | Address Book |
| `h` | History |
| `s` | Settings |
| `Tab` | Navigate between fields |
| `Enter` | Select/Execute |
| `Esc` | Close dialog |

## Using Testnet

### 1. Get Testnet XYM

After creating your wallet, get testnet XYM from:
- https://faucet.testnet.symbol.tools/
- https://testnet.symbol.tools/

### 2. Send a Transaction

1. Press `t` to go to Transfer tab
2. Enter recipient address or select from address book
3. Add mosaics (default: XYM with ID `6BED913FA20223F8`)
4. Enter amount (in micro-XYM: 1 XYM = 1,000,000)
5. Add optional message
6. Review and confirm transaction

### 3. Check Transaction Status

Use your transaction hash to verify on:
- https://testnet.symbol.tools/
- https://explorer.testnet.symbol.tools/

## Configuration

### Node URLs

**Testnet:**
- `http://sym-test-01.opening-line.jp:3000`

**Mainnet:**
- `http://sym-main-01.opening-line.jp:3000`
- `http://symbol.node:3000`

### Data Storage

Wallet data is stored locally:

- **macOS/Unix**: `~/.symbol-quick-wallet/`
  - `wallet.json` - Wallet credentials
  - `address_book.json` - Contact list
  - `config.json` - Application settings
  - `encrypted_private_key.json` - Encrypted backup

- **Windows**: `%USERPROFILE%\.symbol-quick-wallet\`

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run unit tests only
pytest -m unit

# Run with coverage
pytest --cov=src --cov-report=html
```

### Code Quality

```bash
# Run linter
ruff check src/

# Run type checker
ty check src/

# Auto-fix issues
ruff check src/ --fix
```

### Building Package

```bash
# Build distribution
uv build

# Test installation from build
pip install dist/symbol-quick-wallet-*.whl
```

## Security Notes

⚠️ **Important Security Information:**

- **Private Keys**: Stored locally and never shared with external services
- **Encryption**: Use password protection when exporting private keys
- **Backup**: Always backup your encrypted private keys securely
- **Test First**: Always test with small amounts on testnet before using mainnet
- **Network**: Verify node URLs to ensure you're on the correct network

### Recommended Security Practices

1. Never share your private key or encrypted backup password
2. Use strong passwords for encrypted key exports
3. Store encrypted backups offline
4. Keep your wallet data directory private
5. Use hardware wallets for large amounts (future feature)

## Troubleshooting

### Connection Issues

If you can't connect to the network:

1. Check your internet connection
2. Verify the node URL in Settings
3. Try a different node from the Symbol node list
4. Check node status at https://node.symbol.tools/

### Command Mode

The application provides a command mode for quick navigation using the `/` key:

#### Using Command Mode

1. Press `/` to open the command selector
2. Use arrow keys (↑/↓) to select a command
3. Press **Enter** or **✅ Select** to execute the command
4. Press **Esc** or **❌ Cancel** to close

### Available Commands

| Command | Description |
|---------|-------------|
| `/dashboard` or `/d` | Go to Dashboard |
| `/transfer` or `/t` | Go to Transfer |
| `/address-book` or `/a` | Go to Address Book |
| `/history` or `/h` | Go to History |
| `/settings` or `/s` | Go to Settings |

### SSH + tmux Environment
For SSH users, we recommend **Ghostty** terminal for the best experience:

#### Common Issues

1. **Clipboard not working**: Use Ghostty for OSC 52 support
2. **Prompt display issues**: Enable shell integration features

#### Ghostty Configuration

Add to `~/.config/ghostty/config`:
```
shell-integration-features = ssh-terminfo,ssh-env
```

#### tmux Configuration

Add to `~/.tmux.conf`:
```tmux
set -g default-terminal "xterm-ghostty"
set -ga terminal-overrides ",xterm-ghostty:Tc"
set -s set-clipboard on
set -g allow-passthrough on
```

## Command Mode

The application provides a command mode for quick navigation using the `/` key:

### Using Command Mode

1. Press `/` to open the command selector
2. Use arrow keys (↑/↓) to select a command
3. Press **Enter** to execute the command
4. Press **Esc** or **Cancel** to close the command selector

### Available Commands

| Command | Description |
|---------|-------------|
| `/dashboard` or `/d` | Go to Dashboard |
| `/transfer` or `/t` | Go to Transfer |
| `/address-book` or `/a` | Go to Address Book |
| `/history` or `/h` | Go to History |
| `/settings` or `/s` | Go to Settings |

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Ensure all tests pass and code quality checks succeed
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Links

- **Symbol Official Site**: https://symbolplatform.com/
- **Symbol SDK**: https://github.com/symbol/symbol
- **Textual Documentation**: https://textual.textual.io/
- **Symbol Explorer**: https://explorer.symbol.tools/

---

# 日本語

シンプルで安全なTUIベースのSymbolブロックチェーンウォレット（macOS/Linux/Windows対応）

## コンセプト

Symbol Quick Walletは、Symbolブロックチェーン用の最小限で安全、かつ使いやすいウォレットを提供することを目指しています。

- **シンプルさ**: キーボードショートカットを活用したクリーンなTUIインターフェース
- **セキュリティ**: ローカル秘密鍵保存と暗号化オプション
- **プライバシー**: 外部サービスを使用せず、Symbolノードと直接通信
- **アクセシビリティ**: ターミナル環境で動作、SSH経由のリモートアクセスに最適
- **クロスプラットフォーム**: macOS、Linux、Windowsで動作

## インストール

### pip経由（推奨）

```bash
pip install symbol-quick-wallet
```

### uv経由（高速）

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv pip install symbol-quick-wallet
```

### ソースから

```bash
git clone https://github.com/yourusername/symbol-quick-wallet.git
cd symbol-quick-wallet
uv sync
```

## クイックスタート

### 初回起動

```bash
symbol-quick-wallet
```

初回起動時に以下の手順で設定します：

1. **ネットワーク選択**: TestnetまたはMainnetを選択
2. **ウォレット設定**: 新規作成またはインポート

### ウォレットの使用

設定後、以下のタブが表示されます：

- **ダッシュボード**: アドレス、残高、ネットワーク状況の確認
- **送信**: XYMやモザイクの送信
- **アドレス帳**: 連絡先の管理
- **履歴**: トランザクション履歴の表示
- **設定**: ノード設定、ウォレット管理、キーエクスポート

### キーボードショートカット

| キー | 機能 |
|-----|------|
| `q` | 終了 |
| `d` | ダッシュボード |
| `t` | 送信 |
| `a` | アドレス帳 |
| `h` | 履歴 |
| `s` | 設定 |
| `Tab` | フィールド間移動 |
| `Enter` | 選択/実行 |
| `Esc` | ダイアログを閉じる |

## セキュリティ注意事項

⚠️ **重要なセキュリティ情報:**

- **秘密鍵**: ローカルに保存され、外部サービスと共有されません
- **暗号化**: 秘密鍵のエクスポート時はパスワード保護を使用してください
- **バックアップ**: 暗号化された秘密鍵を安全にバックアップしてください
- **テスト優先**: メインネット使用前に、テストネットで必ずテストしてください
- **ネットワーク**: 正しいネットワークに接続していることを確認してください

## ライセンス

MIT License - LICENSEファイルを参照してください

## リンク

- **Symbol公式サイト**: https://symbolplatform.com/
- **Symbol SDK**: https://github.com/symbol/symbol
- **Symbol Explorer**: https://explorer.symbol.tools/
- **Textualドキュメント**: https://textual.textual.io/
