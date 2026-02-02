# rock-paper-scissors

Federated Rock-Paper-Scissors game with SPIFFE mTLS authentication and supply chain security.

## 🎮 Quick Start

### Option 1: Download Pre-Built Signed Binary from GitHub Releases

```bash
# Download the latest release binary and signature bundle
curl -L -o rps-game https://github.com/npaulat99/rock-paper-scissors/releases/latest/download/rps-game
curl -L -o rps-game.cosign.bundle https://github.com/npaulat99/rock-paper-scissors/releases/latest/download/rps-game.cosign.bundle

# Verify the signature before running (supply chain security!)
cosign verify-blob \
  --bundle rps-game.cosign.bundle \
  --certificate-identity-regexp="https://github.com/.+" \
  --certificate-oidc-issuer-regexp="https://token.actions.githubusercontent.com" \
  rps-game

# Make executable and run
chmod +x rps-game
./rps-game --help
```

**Prerequisites:**
- Cosign installed: `curl -fsSL https://github.com/sigstore/cosign/releases/latest/download/cosign-linux-amd64 -o cosign && chmod +x cosign && sudo mv cosign /usr/local/bin/`

**Optional:** Copy binary to your PATH:
```bash
sudo cp rps-game /usr/local/bin/
```

### Option 2: Docker Image

```bash
docker pull ghcr.io/npaulat99/rock-paper-scissors:latest
```

### Option 3: Build from Source

```bash
git clone https://github.com/npaulat99/rock-paper-scissors.git
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

The signed binary is available from **GitHub Releases**:

1. Go to: https://github.com/npaulat99/rock-paper-scissors/releases
2. Download `rps-game` and `rps-game.cosign.bundle`
3. Verify and run:

```bash
# Verify signature (supply chain security requirement!)
cosign verify-blob \
  --bundle rps-game.cosign.bundle \
  --certificate-identity-regexp="https://github.com/.+" \
  --certificate-oidc-issuer-regexp="https://token.actions.githubusercontent.com" \
  rps-game

# Run verified binary
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
  trust_domain = "noah.inter-cloud-thi.de"
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
# Get server trust bundle first
cd ~/spire-1.13.3
sudo ./bin/spire-server bundle show > /tmp/bootstrap-bundle.crt

# Create agent config
sudo tee /opt/spire/agent/agent.conf > /dev/null <<'EOF'
agent {
  data_dir = "/tmp/spire-agent/data"
  log_level = "INFO"
  server_address = "127.0.0.1"
  server_port = "8081"
  socket_path = "/tmp/spire-agent/public/api.sock"
  trust_domain = "noah.inter-cloud-thi.de"
  trust_bundle_path = "/tmp/bootstrap-bundle.crt"
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
TOKEN=$(sudo ./bin/spire-server token generate -spiffeID spiffe://noah.inter-cloud-thi.de/agent/myagent | grep Token | awk '{print $2}')

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

# Register game workload (Unix UID selector)
sudo ./bin/spire-server entry create \
  -spiffeID spiffe://noah.inter-cloud-thi.de/game-server-alice \
  -parentID spiffe://noah.inter-cloud-thi.de/agent/myagent \
  -selector unix:uid:$(id -u)

# Verify registration
sudo ./bin/spire-server entry show
```

**Important:** The selector `unix:uid:$(id -u)` means any process running as your user can obtain this SVID.

### 2.2 Generate Certificates with SPIRE Agent API

The game application will fetch certificates directly from the SPIRE agent using the go-spiffe library. No additional tools needed!

**For testing that the workload can get certificates:**

```bash
# Create cert directory (the game will use this)
mkdir -p ~/certs

# Test fetching SVID using SPIRE agent (run as your user, NOT sudo)
SPIFFE_ENDPOINT_SOCKET=/tmp/spire-agent/public/api.sock \
  ~/spire-1.13.3/bin/spire-agent api fetch x509 \
  -write ~/certs/

# Verify certs exist
ls -lh ~/certs/
```

You should see `svid.0.pem`, `svid.0.key`, and `bundle.0.pem`.

**Rename files to expected names:**

```bash
cd ~/certs
mv svid.0.pem svid.pem
mv svid.0.key svid_key.pem
mv bundle.0.pem svid_bundle.pem
ls -la
```

You should now see: `svid.pem`, `svid_key.pem`, `svid_bundle.pem`

**Note:** The rock-paper-scissors Docker container will fetch certificates automatically when it runs - these manual steps are just for verification.

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
# Pull the image from GHCR
docker pull ghcr.io/npaulat99/rock-paper-scissors:latest

# Or build locally if you have the repo
cd ~/rock-paper-scissors
docker build -f src/docker/Dockerfile -t rock-paper-scissors:latest .
```

### 4.2 Run in Serve Mode (Wait for Challenges)

```bash
# Run server in interactive mode (Alice)
docker run -it --rm \
  --network host \
  -v ~/certs:/app/certs:ro \
  -e RPS_MODE=serve \
  -e RPS_BIND=0.0.0.0:9002 \
  -e RPS_SPIFFE_ID=spiffe://noah.inter-cloud-thi.de/game-server-alice \
  -e RPS_MTLS=1 \
  ghcr.io/npaulat99/rock-paper-scissors:latest
```

**What happens:**
- Server listens on port 9002
- When a peer sends a challenge, you'll see a prompt to choose your move
- Enter `r` (rock), `p` (paper), or `s` (scissors)

### 4.3 Challenge a Peer (Initiate Game)

**In another terminal or VM:**

```bash
# Challenge another player (Bob challenges Alice)
docker run -it --rm \
  --network host \
  -v ~/certs:/app/certs:ro \
  -e RPS_MODE=play \
  -e RPS_BIND=0.0.0.0:9003 \
  -e RPS_SPIFFE_ID=spiffe://noah.inter-cloud-thi.de/game-server-bob \
  -e RPS_PEER_URL=https://localhost:9002 \
  -e RPS_PEER_ID=spiffe://noah.inter-cloud-thi.de/game-server-alice \
  -e RPS_PUBLIC_URL=https://localhost:9003 \
  -e RPS_MTLS=1 \
  ghcr.io/npaulat99/rock-paper-scissors:latest
```

**What happens:**
- You'll be prompted to choose your move for round 1
- After you choose, the challenger sends the commitment to the peer
- Peer chooses their move and sends it back
- You reveal your move, and the outcome is shown
- If it's a tie, you're prompted again for the next round
- When someone wins, scores are updated

### 4.4 View Scores

Scores are tracked in-memory during the game session and displayed after each match. You can also view the scoreboard at any time by pressing `Ctrl+C` to see final scores.

---

## Part 5: Testing Locally (Single VM, Two Identities)

To test locally with two identities, you need **separate certificates** for each player. The easiest approach is to use the **same SPIFFE ID** for both (self-play) or run without mTLS for local testing.

### Option A: Self-Play (Same Identity)

Test the game logic without federation. Both containers use the same identity:

**Terminal 1 - Server:**
```bash
docker run -it --rm \
  --network host \
  -v ~/certs:/app/certs:ro \
  -e RPS_MODE=serve \
  -e RPS_BIND=0.0.0.0:9002 \
  -e RPS_SPIFFE_ID=spiffe://noah.inter-cloud-thi.de/game-server-alice \
  -e RPS_MTLS=1 \
  ghcr.io/npaulat99/rock-paper-scissors:latest
```

**Terminal 2 - Challenger (same identity challenges itself for testing):**
```bash
docker run -it --rm \
  --network host \
  -v ~/certs:/app/certs:ro \
  -e RPS_MODE=play \
  -e RPS_BIND=0.0.0.0:9003 \
  -e RPS_SPIFFE_ID=spiffe://noah.inter-cloud-thi.de/game-server-alice \
  -e RPS_PEER_URL=https://localhost:9002 \
  -e RPS_PEER_ID=spiffe://noah.inter-cloud-thi.de/game-server-alice \
  -e RPS_PUBLIC_URL=https://localhost:9003 \
  -e RPS_MTLS=1 \
  ghcr.io/npaulat99/rock-paper-scissors:latest
```

### Option B: Two Identities with Container Selectors

For true two-identity testing, register workloads with **container selectors** instead of UID selectors:

```bash
cd ~/spire-1.13.3

# Register Alice (container selector)
sudo ./bin/spire-server entry create \
  -spiffeID spiffe://noah.inter-cloud-thi.de/game-server-alice \
  -parentID spiffe://noah.inter-cloud-thi.de/agent/myagent \
  -selector docker:label:player:alice

# Register Bob (container selector)  
sudo ./bin/spire-server entry create \
  -spiffeID spiffe://noah.inter-cloud-thi.de/game-server-bob \
  -parentID spiffe://noah.inter-cloud-thi.de/agent/myagent \
  -selector docker:label:player:bob
```

Then run containers with labels and mount the SPIRE agent socket:
```bash
# This requires spiffe-helper or go-spiffe in the container
# See Part 6 (Kubernetes) for production deployment with sidecar pattern
```

### Option C: Federation with Another Team (Recommended)

The proper way to test different identities is with **federation between trust domains**. See Part 3 for federation setup with a peer's VM.

---

## Part 6: Kubernetes Deployment

For production deployments, Kubernetes manifests are provided in `src/k8s/`.

### 6.1 Prerequisites

- Kubernetes cluster with SPIRE deployed
- SPIRE agent running as DaemonSet with workload attestor

### 6.2 Deploy the Game

```bash
# Apply all manifests using Kustomize
kubectl apply -k src/k8s/

# Verify deployment
kubectl -n rps-game get pods
kubectl -n rps-game get svc

# Check logs
kubectl -n rps-game logs -l app=rps-game -c rps-game
```

### 6.3 Register Kubernetes Workload with SPIRE

```bash
# Register the workload using Kubernetes selectors
spire-server entry create \
  -spiffeID spiffe://noah.inter-cloud-thi.de/game-server \
  -parentID spiffe://noah.inter-cloud-thi.de/spire/agent/k8s_psat/<cluster-name> \
  -selector k8s:ns:rps-game \
  -selector k8s:sa:rps-game
```

### 6.4 Access the Game

```bash
# Get NodePort
kubectl -n rps-game get svc rps-game

# The service is exposed on port 30902
# Access: https://<node-ip>:30902/v1/rps/scores
```

---

## Part 7: Move Signing (Optional)

For enhanced security, game moves can be cryptographically signed using Sigstore or SSH keys.

### 7.1 Sigstore (Keyless) Signing

Requires Cosign and OIDC authentication:

```python
from move_signing import sign_move_sigstore, verify_move_sigstore

# Sign a move
signed = sign_move_sigstore(
    move="rock",
    match_id="abc123",
    round=1,
    signer_spiffe_id="spiffe://noah.inter-cloud-thi.de/game-server-alice",
)

# Verify the move
is_valid = verify_move_sigstore(signed)
```

### 7.2 SSH Key Signing (Offline)

For environments without internet access:

```python
from move_signing import sign_move_ssh, verify_move_ssh

# Sign with SSH key
signed = sign_move_ssh(
    move="paper",
    match_id="abc123",
    round=1,
    signer_spiffe_id="spiffe://noah.inter-cloud-thi.de/game-server-alice",
    ssh_key_path="~/.ssh/id_ed25519",
)

# Create allowed_signers file with trusted public keys
# Format: spiffe://domain/identity ssh-ed25519 AAAA...
is_valid = verify_move_ssh(signed, "~/.config/rps/allowed_signers")
```

---

## Project Structure

```
rock-paper-scissors/
├── .github/workflows/
│   └── supply-chain.yml     # CI/CD pipeline with signing & attestations
├── attestations/            # SLSA provenance, SBOM, vulnerability reports
├── scripts/
│   ├── download-and-verify-binary.sh  # Download & verify signed binary
│   └── demo/                           # Demo helper scripts
├── src/
│   ├── app/
│   │   ├── cli.py           # CLI entrypoint (serve, play, scores)
│   │   ├── commit_reveal.py # SHA256 commitment scheme
│   │   ├── http_api.py      # HTTP server with mTLS
│   │   ├── move_signing.py  # Sigstore/SSH move signing
│   │   ├── protocol.py      # Game rules
│   │   ├── rps_client.py    # HTTP client for challenges
│   │   ├── scoreboard.py    # Score tracking per SPIFFE ID
│   │   └── spiffe_mtls.py   # SPIFFE mTLS SSL contexts
│   ├── docker/
│   │   └── Dockerfile       # Container image
│   └── k8s/                 # Kubernetes manifests
│       ├── kustomization.yaml
│       ├── namespace.yaml
│       ├── deployment.yaml
│       ├── service.yaml
│       └── ...
└── tests/
    └── test_protocol.py     # Unit tests
```
