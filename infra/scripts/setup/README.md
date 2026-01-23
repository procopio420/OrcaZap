# WireGuard Key Generation Scripts

## Overview

These scripts help generate WireGuard keys on each server and collect them for use in the inventory file.

## Scripts

### `generate_wireguard_keys.sh`

Generates WireGuard keys on a single server. Can be run locally on the server or via SSH.

**Usage:**
```bash
# On the server directly
./generate_wireguard_keys.sh [output_dir]

# Default output: /tmp/wireguard-keys/
```

**Output:**
- `privatekey` - WireGuard private key
- `publickey` - WireGuard public key

### `setup_all_wireguard_keys.sh`

Generates WireGuard keys on all three VPS servers via SSH and collects them into a single file.

**Prerequisites:**
- `SSH_PRIVATE_KEY` environment variable set (or SSH agent)
- `INVENTORY_FILE` environment variable pointing to `infra/inventory/hosts.env`
- SSH access to all three VPS servers

**Usage:**
```bash
export SSH_PRIVATE_KEY="$(cat docs/infra/deploy_key)"
export INVENTORY_FILE="infra/inventory/hosts.env"

./setup_all_wireguard_keys.sh [--output wireguard-keys.env]
```

**Output:**
- Creates `wireguard-keys.env` (or custom filename) with all WireGuard keys
- Format: `VPS*_WIREGUARD_PRIVATE_KEY` and `VPS*_WIREGUARD_PUBLIC_KEY`

## Manual Process

If you prefer to generate keys manually:

1. **On each server**, run:
   ```bash
   wg genkey | tee privatekey | wg pubkey > publickey
   ```

2. **Copy the keys** from each server:
   - VPS1: `privatekey` → `VPS1_WIREGUARD_PRIVATE_KEY`
   - VPS1: `publickey` → `VPS1_WIREGUARD_PUBLIC_KEY`
   - Repeat for VPS2 and VPS3

3. **Update** `infra/inventory/hosts.env` with the keys

## Automated Process

1. **Set environment variables:**
   ```bash
   export SSH_PRIVATE_KEY="$(cat docs/infra/deploy_key)"
   export INVENTORY_FILE="infra/inventory/hosts.env"
   ```

2. **Run the setup script:**
   ```bash
   cd infra/scripts/setup
   ./setup_all_wireguard_keys.sh
   ```

3. **Merge keys into hosts.env:**
   ```bash
   # The script creates wireguard-keys.env
   # Copy the key values into infra/inventory/hosts.env
   cat wireguard-keys.env
   # Then manually update hosts.env or use sed/awk to merge
   ```

## Security Notes

- **Never commit** `hosts.env` or `wireguard-keys.env` to git
- WireGuard private keys are sensitive - keep them secure
- The generated keys are unique per server
- Keys are generated using `wg genkey` (cryptographically secure)


