# PyPI Publishing Guide

## Prerequisites

Before publishing to PyPI, make sure you have:

1. **PyPI Account**: Create an account at https://pypi.org/account/register/
2. **API Token**: Generate an API token for package publishing
   - Go to https://pypi.org/manage/account/token/
   - Create a new token with "Entire account" scope
   - Save the token securely (you'll need it for uploading)

3. **Install Publishing Tools**:
   ```bash
   uv pip install --dev twine build
   ```

## Build Package

Before publishing, always build and verify the package:

```bash
# Clean previous builds
rm -rf dist/ build/ src/symbol_quick_wallet.egg-info/

# Build the package
uv build

# Verify the contents
unzip -l dist/symbol_quick_wallet-*.whl
```

## Check Package

Use `twine check` to verify the package description:

```bash
twine check dist/*
```

This will check:
- Long description rendering (README.md)
- Metadata validity
- Package structure

## Test Package Locally

Before publishing to PyPI, test the package locally:

```bash
# Create a virtual environment for testing
python -m venv test_env
source test_env/bin/activate

# Install the wheel
pip install dist/symbol_quick_wallet-0.6.0-py3-none-any.whl

# Test the command
symbol-quick-wallet --help 2>&1 | head -5

# Test import
python -c "from src.__main__ import main; print('Import successful!')"

# Deactivate and cleanup
deactivate
rm -rf test_env/
```

## Publishing to TestPyPI (Recommended)

Before publishing to PyPI, test on TestPyPI:

1. **Register for TestPyPI**: https://test.pypi.org/account/register/

2. **Publish to TestPyPI**:
   ```bash
   # Build the package
   uv build

   # Upload to TestPyPI
   twine upload --repository testpypi dist/*
   ```

3. **Test Installation from TestPyPI**:
   ```bash
   # Install from TestPyPI
   pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ symbol-quick-wallet

   # Or using uv
   uv pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ symbol-quick-wallet
   ```

## Publishing to PyPI

Once verified on TestPyPI, publish to PyPI:

1. **Build the package**:
   ```bash
   uv build
   ```

2. **Upload to PyPI**:
   ```bash
   # You'll be prompted for your API token
   twine upload dist/*
   ```

   Or use a `~/.pypirc` file with your credentials:
   ```ini
   [pypi]
   username = __token__
   password = your-api-token-here
   ```

3. **Verify on PyPI**:
   - Go to https://pypi.org/project/symbol-quick-wallet/
   - Check that the package is listed

## Installation from PyPI

After publishing, users can install with:

```bash
# Using pip
pip install symbol-quick-wallet

# Using uv
uv pip install symbol-quick-wallet

# Run the application
symbol-quick-wallet
```

## Troubleshooting

### "File already exists" Error

If you get an error saying the file already exists:
- Increment the version in `pyproject.toml`
- Rebuild: `uv build`
- Upload again

### "403 Forbidden" Error

This usually means:
- Invalid API token
- Package name already exists (and you don't have permission)
- Token doesn't have upload permissions

### "400 Bad Request" Error

Common causes:
- Invalid version number format
- Missing required metadata
- Invalid package structure

Check the error message carefully for details.

### README not rendering correctly

Ensure:
- README.md is included in the package
- `readme = "README.md"` is set in pyproject.toml
- Long description is set to appropriate content type (Markdown)

## Version Management

When publishing a new version:

1. Update version in `pyproject.toml`:
   ```toml
   version = "0.7.0"  # New version
   ```

2. Update CHANGELOG or release notes

3. Commit changes:
   ```bash
   git add pyproject.toml README.md
   git commit -m "Bump version to 0.7.0"
   git tag v0.7.0
   git push origin main --tags
   ```

4. Build and publish:
   ```bash
   uv build
   twine upload dist/*
   ```

## Security Best Practices

1. **Never commit API tokens**: Use environment variables or `~/.pypirc`
2. **Use trusted tokens**: Create project-specific tokens when possible
3. **Review metadata**: Check all metadata before publishing
4. **Verify checksums**: Verify package integrity after upload

## Additional Resources

- [PyPI User Guide](https://packaging.python.org/tutorials/packaging-projects/)
- [Twine Documentation](https://twine.readthedocs.io/)
- [TestPyPI](https://test.pypi.org/)
