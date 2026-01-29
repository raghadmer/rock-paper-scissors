# rock-paper-scissors

Federated Rock-Paper-Scissors game with SPIFFE mTLS authentication and supply chain security.

## 🎮 Quick Start

### Option 1: Download Pre-Built Signed Binary (Recommended)

```bash
# Download and verify the signed binary from GitHub Actions
bash <(curl -s https://raw.githubusercontent.com/YOUR-USERNAME/rock-paper-scissors/main/scripts/download-and-verify-binary.sh)
```

This script will:
1. Download the latest binary from GitHub Actions artifacts
2. Verify the Cosign signature (keyless signing)
3. Extract the binary to a temporary directory
4. Run a quick test

### Option 2: Docker Image

```bash
docker pull ghcr.io/YOUR-USERNAME/rock-paper-scissors:latest
```

### Option 3: Build from Source

```bash
git clone https://github.com/YOUR-USERNAME/rock-paper-scissors.git
cd rock-paper-scissors
pip install -r requirements.txt
python src/app/cli.py --help
```

---

## 📦 Supply Chain Security

This project demonstrates complete supply chain security:

✅ **Phase 1 - Scanning:** Trivy scans (source, Docker, IaC, image)  
✅ **Phase 2 - Attestations:** SLSA provenance, SBOM, vulnerability attestations  
✅ **Phase 3 - Signing:** Cosign keyless signing (GitHub OIDC)  
✅ **Phase 4 - CI/CD:** Automated GitHub Actions pipeline  

**Bonus Features:**
- ✅ Game binary built in CI/CD (PyInstaller)
- ✅ Binary downloadable from pipeline (GitHub Actions artifacts)
- ✅ Signature verification before execution (Cosign blob signing)

### Manual Download & Verify

If you prefer manual steps:

```bash
# 1. Download artifact from GitHub Actions
gh run download <RUN_ID> --repo YOUR-USERNAME/rock-paper-scissors --name rps-game-binary

# 2. Verify signature
cosign verify-blob \
  --bundle rps-game.cosign.bundle \
  --certificate-identity-regexp="https://github.com/.+" \
  --certificate-oidc-issuer-regexp="https://token.actions.githubusercontent.com" \
  rps-game

# 3. Run
chmod +x rps-game
./rps-game --help
```

---

## Prerequisites

- Ubuntu VM with sudo access
- Docker installed
- Internet connectivity
- Another team's VM for federation (or simulate locally)

---

## Part 1: SPIRE Infrastructure Setup

### 1.1 Install SPIRE Server and Agent

```bash
# Download SPIRE 1.13.3
cd ~
wget https://github.com/spiffe/spire/releases/download/v1.13.3/spire-1.13.3-linux-amd64-musl.tar.gz
tar -xzf spire-1.13.3-linux-amd64-musl.tar.gz
cd spire-1.13.3

# Create config directories
sudo mkdir -p /opt/spire/server /opt/spire/agent
sudo mkdir -p /tmp/spire-server /tmp/spire-agent
```

### 1.2 Configure SPIRE Server

```bash
# Create server config
sudo tee /opt/spire/server/server.conf > /dev/null <<'EOF'
server {
  bind_address = "0.0.0.0"
  bind_port = "8081"
  trust_domain = "YOUR-TRUST-DOMAIN.example.com"
  data_dir = "/tmp/spire-server/data"
  log_level = "INFO"
}

plugins {
  DataStore "sql" {
    plugin_data {
      database_type = "sqlite3"
      connection_string = "/tmp/spire-server/data/datastore.sqlite3"
    }
  }
  NodeAttestor "join_token" {
    plugin_data {}
  }
  KeyManager "disk" {
    plugin_data {
      keys_path = "/tmp/spire-server/data/keys.json"
    }
  }
}
EOF

# Replace YOUR-TRUST-DOMAIN with your actual domain (e.g., alice.inter-cloud-thi.de)
```

### 1.3 Configure SPIRE Agent

```bash
# Create agent config
sudo tee /opt/spire/agent/agent.conf > /dev/null <<'EOF'
agent {
  data_dir = "/tmp/spire-agent/data"
  log_level = "INFO"
  server_address = "127.0.0.1"
  server_port = "8081"
  socket_path = "/tmp/spire-agent/public/api.sock"
  trust_domain = "YOUR-TRUST-DOMAIN.example.com"
}

plugins {
  NodeAttestor "join_token" {
    plugin_data {}
  }
  KeyManager "disk" {
    plugin_data {
      directory = "/tmp/spire-agent/data"
    }
  }
  WorkloadAttestor "unix" {
    plugin_data {}
  }
}
EOF

# Replace YOUR-TRUST-DOMAIN with the same domain as server
```

### 1.4 Start SPIRE Server

```bash
# Start server
cd ~/spire-1.13.3
sudo ./bin/spire-server run -config /opt/spire/server/server.conf &

# Wait for server to start
sleep 3

# Verify server is running
sudo ./bin/spire-server healthcheck
```

### 1.5 Generate Join Token and Start Agent

```bash
# Generate join token for agent
TOKEN=$(sudo ./bin/spire-server token generate -spiffeID spiffe://YOUR-TRUST-DOMAIN.example.com/agent/myagent | grep Token | awk '{print $2}')

# Start agent with join token
sudo ./bin/spire-agent run -config /opt/spire/agent/agent.conf -joinToken $TOKEN &

# Wait for agent to start
sleep 3

# Verify socket exists
ls -la /tmp/spire-agent/public/api.sock
```

---

## Part 2: Game Workload Registration

### 2.1 Register Game Workload

Choose your workload SPIFFE ID (e.g., `/game-server-alice`):

```bash
cd ~/spire-1.13.3

# Register game workload (Unix UID selector - replace 1000 with your UID)
sudo ./bin/spire-server entry create \
  -spiffeID spiffe://YOUR-TRUST-DOMAIN.example.com/game-server-alice \
  -parentID spiffe://YOUR-TRUST-DOMAIN.example.com/agent/myagent \
  -selector unix:uid:$(id -u)

# Verify registration
sudo ./bin/spire-server entry show
```

**Important:** The selector `unix:uid:$(id -u)` means any process running as your user can obtain this SVID.

### 2.2 Install spiffe-helper

```bash
# Download spiffe-helper
cd ~
wget https://github.com/spiffe/spiffe-helper/releases/download/v0.9.2/spiffe-helper_0.9.2_linux_x86_64.tar.gz
tar -xzf spiffe-helper_0.9.2_linux_x86_64.tar.gz
sudo mv spiffe-helper /usr/local/bin/
sudo chmod +x /usr/local/bin/spiffe-helper
```

### 2.3 Generate Certificates

```bash
# Create cert directory
mkdir -p ~/certs

# Create spiffe-helper config
cat > ~/spiffe-helper.conf <<EOF
agent_address = "/tmp/spire-agent/public/api.sock"
cmd = ""
cmd_args = ""
cert_dir = "$HOME/certs"
renew_signal = ""
svid_file_name = "svid.pem"
svid_key_file_name = "svid_key.pem"
svid_bundle_file_name = "svid_bundle.pem"
EOF

# Fetch certificates
spiffe-helper -config ~/spiffe-helper.conf &
HELPER_PID=$!
sleep 2
kill $HELPER_PID

# Verify certs exist
ls -lh ~/certs/
```

You should see `svid.pem`, `svid_key.pem`, and `svid_bundle.pem`.

---

## Part 3: Federation Setup (Cross-Domain Play)

**This section is for federating with another team's trust domain.**

### 3.1 Export Your Trust Bundle

```bash
cd ~/spire-1.13.3

# Export your trust bundle
sudo ./bin/spire-server bundle show -format spiffe > ~/my-trust-bundle.json

# Share this file with your peer (e.g., via email, USB, or secure file transfer)
cat ~/my-trust-bundle.json
```

### 3.2 Import Peer's Trust Bundle

**After receiving peer's trust bundle (e.g., `peer-trust-bundle.json`):**

```bash
cd ~/spire-1.13.3

# Set the peer trust bundle
sudo ./bin/spire-server bundle set \
  -format spiffe \
  -id spiffe://PEER-TRUST-DOMAIN.example.com \
  < ~/peer-trust-bundle.json

# Verify federation
sudo ./bin/spire-server bundle list
```

You should see both your trust domain and the peer's trust domain listed.

---

## Part 4: Pull and Run the Game

### 4.1 Pull Docker Image

```bash
# Pull your team's image from GHCR (replace with your image)
docker pull ghcr.io/YOUR-USERNAME/rock-paper-scissors:latest

# Or build locally if you have the repo
cd ~/rock-paper-scissors
docker build -f src/docker/Dockerfile -t rock-paper-scissors:latest .
```

### 4.2 Run in Serve Mode (Wait for Challenges)

```bash
# Run server in interactive mode
docker run -it --rm \
  --network host \
  -v ~/certs:/app/certs:ro \
  ghcr.io/YOUR-USERNAME/rock-paper-scissors:latest \
  serve \
  --bind 0.0.0.0:9002 \
  --spiffe-id spiffe://YOUR-TRUST-DOMAIN.example.com/game-server-alice \
  --mtls \
  --cert-dir /app/certs
```

**What happens:**
- Server listens on port 9002
- When a peer sends a challenge, you'll see a prompt to choose your move
- Enter `r` (rock), `p` (paper), or `s` (scissors)

### 4.3 Challenge a Peer (Initiate Game)

**In another terminal or VM:**

```bash
# Challenge another player
docker run -it --rm \
  --network host \
  -v ~/certs:/app/certs:ro \
  ghcr.io/YOUR-USERNAME/rock-paper-scissors:latest \
  play \
  --bind 0.0.0.0:9003 \
  --spiffe-id spiffe://YOUR-TRUST-DOMAIN.example.com/game-server-alice \
  --peer https://PEER-IP:9002 \
  --peer-id spiffe://PEER-TRUST-DOMAIN.example.com/game-server-bob \
  --public-url https://YOUR-PUBLIC-IP:9003 \
  --mtls \
  --cert-dir /app/certs
```

**What happens:**
- You'll be prompted to choose your move for round 1
- After you choose, the challenger sends the commitment to the peer
- Peer chooses their move and sends it back
- You reveal your move, and the outcome is shown
- If it's a tie, you're prompted again for the next round
- When someone wins, scores are updated

### 4.4 View Scores

```bash
# View your local scoreboard
docker run -it --rm \
  -v ~/.rps:/root/.rps \
  ghcr.io/YOUR-USERNAME/rock-paper-scissors:latest \
  scores
```

---

## Part 5: Testing Locally (Single VM, Two Identities)

If you want to test without a second VM:

### 5.1 Register Second Workload

```bash
cd ~/spire-1.13.3

# Register second identity
sudo ./bin/spire-server entry create \
  -spiffeID spiffe://YOUR-TRUST-DOMAIN.example.com/game-server-bob \
  -parentID spiffe://YOUR-TRUST-DOMAIN.example.com/agent/myagent \
  -selector unix:uid:$(id -u)
```

### 5.2 Generate Certs for Second Identity

```bash
# Create second cert directory
mkdir -p ~/certs-bob

# Create second spiffe-helper config
cat > ~/spiffe-helper-bob.conf <<EOF
agent_address = "/tmp/spire-agent/public/api.sock"
cmd = ""
cmd_args = ""
cert_dir = "$HOME/certs-bob"
renew_signal = ""
svid_file_name = "svid.pem"
svid_key_file_name = "svid_key.pem"
svid_bundle_file_name = "svid_bundle.pem"
EOF

# Fetch certs (requires bob's SPIFFE ID to be registered)
# This won't work automatically - you'd need workload attestation to distinguish
# For testing, manually create a process that requests bob's identity
```

**Note:** For true local testing with two identities, you need separate processes with different selectors (e.g., different UIDs or container IDs). Simpler approach: use two VMs.
