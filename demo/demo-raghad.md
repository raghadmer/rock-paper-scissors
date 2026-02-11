# rock-paper-scissors

Federated Rock-Paper-Scissors game with SPIFFE mTLS authentication and supply chain security.

## Overview

A peer-to-peer game where each player runs an interactive server that can **simultaneously receive and issue challenges**. Authentication uses SPIFFE mTLS with cross-domain federation.

### Architecture

- Each player runs **one** interactive process (no separate serve/play modes)
- The process listens for incoming challenges AND lets you issue challenges from a command prompt
- All communication uses the **commit-reveal protocol** over SPIFFE mTLS
- Scores are tracked per SPIFFE ID and queryable via HTTPS

### Commit-Reveal Protocol (3 Messages)

1. **Challenge** (Challenger → Responder): `SHA256(move + salt)` commitment
2. **Response** (Responder → Challenger): Responder's plaintext move
3. **Reveal** (Challenger → Responder): Challenger's move + salt for verification

---

## Quick Start

### Option 1: Docker Image (Recommended)

```bash
docker pull ghcr.io/npaulat99/rock-paper-scissors:latest
```

### Option 2: Download Signed Binary

```bash
curl -L -o rps-game https://github.com/npaulat99/rock-paper-scissors/releases/latest/download/rps-game
curl -L -o rps-game.cosign.bundle https://github.com/npaulat99/rock-paper-scissors/releases/latest/download/rps-game.cosign.bundle

cosign verify-blob \
  --bundle rps-game.cosign.bundle \
  --certificate-identity-regexp="https://github.com/.+" \
  --certificate-oidc-issuer-regexp="https://token.actions.githubusercontent.com" \
  rps-game

chmod +x rps-game
./rps-game --help
```

### Option 3: Build from Source

```bash
git clone https://github.com/npaulat99/rock-paper-scissors.git
cd rock-paper-scissors
pip install -r requirements.txt
python src/app/cli.py --help
```

---

## Supply Chain Security

✅ **Phase 1** — Trivy scanning (source, Docker, IaC, image)
✅ **Phase 2** — SLSA provenance, SBOM, vulnerability attestations
✅ **Phase 3** — Cosign keyless signing (GitHub OIDC)
✅ **Phase 4** — Automated GitHub Actions CI/CD pipeline
✅ **Bonus** — Binary built in CI, downloadable from pipeline, signature verification

---

## Demo Checklist

The live demo shows these four steps:

| Nr. | Step | Points | What to Show |
|------|------------|--------|--------------|
| 1 | Single Trust Domain | 7 | SPIRE running, game starts with mTLS, SPIFFE ID in banner |
| 2 | Visible SPIFFE IDs | 5 | SPIFFE URI in startup + peer identity on challenge |
| 3 | Score Tracking | 3 | Play a round, run `scores` command |
| 4 | Federated Reconfiguration | 7 | Import peer bundle, re-register entry, play cross-domain |

**Bonus items** (show if time permits): ACME scoreboard, move signing, supply chain verification.

---

## Reference Values

Replace placeholders in commands below with your own values:

| Placeholder | Noah | Raghad |
|-------------|------|--------|
| `raghad.inter-cloud-thi.de` | `noah.inter-cloud-thi.de` | `raghad.inter-cloud-thi.de` |
| `4.185.211.9` | `4.185.66.130` | `4.185.211.9` |
| `raghad` | `noah` | `raghad` |

---

# SPIRE Setup (Both Players)

## 1. Install SPIRE

```bash
cd ~
wget https://github.com/spiffe/spire/releases/download/v1.13.3/spire-1.13.3-linux-amd64-musl.tar.gz
tar -xzf spire-1.13.3-linux-amd64-musl.tar.gz
cd spire-1.13.3
sudo mkdir -p /opt/spire/server /opt/spire/agent
sudo mkdir -p /tmp/spire-server /tmp/spire-agent
```

## 2. Configure SPIRE Server

```bash
sudo tee /opt/spire/server/server.conf > /dev/null <<'EOF'
server {
  bind_address = "0.0.0.0"
  bind_port = "8081"
  trust_domain = "raghad.inter-cloud-thi.de"
  data_dir = "/tmp/spire-server/data"
  log_level = "INFO"

  federation {
    bundle_endpoint {
      address = "0.0.0.0"
      port = 8443
    }
  }
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
```

> **Replace `raghad.inter-cloud-thi.de`** with your trust domain (e.g. `noah.inter-cloud-thi.de`).

## 3. Configure SPIRE Agent

```bash
sudo tee /opt/spire/agent/agent.conf > /dev/null <<'EOF'
agent {
  data_dir = "/tmp/spire-agent/data"
  log_level = "INFO"
  server_address = "127.0.0.1"
  server_port = "8081"
  socket_path = "/tmp/spire-agent/public/api.sock"
  trust_domain = "raghad.inter-cloud-thi.de"
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

> **Replace `raghad.inter-cloud-thi.de`** with the same trust domain used in the server config.

## 4. Start SPIRE Server

```bash
cd ~/spire-1.13.3

sudo pkill -f spire-server || true
sudo pkill -f spire-agent || true
sleep 2

sudo rm -f /tmp/spire-server/private/api.sock
sudo rm -f /tmp/spire-agent/public/api.sock
sudo mkdir -p /tmp/spire-server/data
sudo mkdir -p /tmp/spire-agent/data /tmp/spire-agent/public

sudo nohup ./bin/spire-server run -config /opt/spire/server/server.conf > /tmp/spire-server.log 2>&1 &
sleep 5

sudo ./bin/spire-server healthcheck
sudo ./bin/spire-server bundle show > /tmp/bootstrap-bundle.crt
```

## 5. Start SPIRE Agent

```bash
cd ~/spire-1.13.3

TOKEN=$(sudo ./bin/spire-server token generate \
  -spiffeID spiffe://raghad.inter-cloud-thi.de/agent/myagent \
  | grep Token | awk '{print $2}')
echo "Token: $TOKEN"

sudo nohup ./bin/spire-agent run \
  -config /opt/spire/agent/agent.conf \
  -joinToken $TOKEN > /tmp/spire-agent.log 2>&1 &
sleep 5

ls -la /tmp/spire-agent/public/api.sock
```

## 6. Register Workload (Single Domain — No Federation Yet)

> **Demo Phase 1**: Register the workload **without** `-federatesWith`.
> Federation is added later to demonstrate the reconfiguration step.

```bash
cd ~/spire-1.13.3

# Clean up any stale entries
sudo ./bin/spire-server entry show
# sudo ./bin/spire-server entry delete -entryID <ID>  # repeat for each

# Create workload entry — single trust domain only
sudo ./bin/spire-server entry create \
  -spiffeID spiffe://raghad.inter-cloud-thi.de/game-server-raghad \
  -parentID spiffe://raghad.inter-cloud-thi.de/agent/myagent \
  -selector unix:uid:$(id -u)

# Verify — should NOT show FederatesWith
sudo ./bin/spire-server entry show
```

## 7. Fetch Certificates

The agent was started **before** the workload entry was created, so restart
it to pick up the new entry:

```bash
cd ~/spire-1.13.3

# Restart agent so it discovers the entry from step 6
sudo pkill -f spire-agent
sleep 3
sudo rm -rf /tmp/spire-agent/data/*
sudo rm -f /tmp/spire-agent/public/api.sock

TOKEN=$(sudo ./bin/spire-server token generate \
  -spiffeID spiffe://raghad.inter-cloud-thi.de/agent/myagent \
  | grep Token | awk '{print $2}')
sudo nohup ./bin/spire-agent run \
  -config /opt/spire/agent/agent.conf \
  -joinToken $TOKEN > /tmp/spire-agent.log 2>&1 &
sleep 30

# Verify agent picked up the entry — look for "Creating X509-SVID"
sudo tail -20 /tmp/spire-agent.log

# Fetch certs
mkdir -p ~/certs && rm -f ~/certs/*
SPIFFE_ENDPOINT_SOCKET=/tmp/spire-agent/public/api.sock \
  ./bin/spire-agent api fetch x509 -write ~/certs/

ls ~/certs/
# Expected: svid.0.pem  svid.0.key  bundle.0.pem
# (no federated_bundle yet — single domain only)

# Prepare cert files for the game
cp ~/certs/bundle.0.pem ~/certs/svid_bundle.pem
mv ~/certs/svid.0.pem ~/certs/svid.pem
mv ~/certs/svid.0.key ~/certs/svid_key.pem

# Should show 1 CA (your own)
grep -c "BEGIN CERTIFICATE" ~/certs/svid_bundle.pem
```

> **Still "no identity issued"?** Check: `sudo ./bin/spire-server entry show`
> — the entry's selector must be `unix:uid:$(id -u)` matching your current user.

---

# Demo Phase 1: Single Trust Domain

Both players complete steps 1–7 above with **their own trust domains**, then start the game.

## Run the Game

### Option A: Signed Binary

```bash
./rps-game \
  --bind 0.0.0.0:9002 \
  --spiffe-id spiffe://raghad.inter-cloud-thi.de/game-server-raghad \
  --public-url https://4.185.211.9:9002 \
  --mtls --cert-dir ~/certs \
  --sign-moves
```

### Option B: Docker

```bash
docker run -it --rm \
  --network host \
  -v ~/certs:/app/certs:ro \
  -e RPS_BIND=0.0.0.0:9002 \
  -e RPS_SPIFFE_ID=spiffe://raghad.inter-cloud-thi.de/game-server-raghad \
  -e RPS_PUBLIC_URL=https://4.185.211.9:9002 \
  -e RPS_MTLS=1 \
  -e RPS_SIGN_MOVES=1 \
  ghcr.io/npaulat99/rock-paper-scissors:latest
```

### What the Demo Shows

The startup banner displays your SPIFFE identity, the mTLS status, and move signing:

```text
============================================================
  Rock-Paper-Scissors — Interactive Mode
  SPIFFE ID : spiffe://noah.inter-cloud-thi.de/game-server-noah
  Listening : https://0.0.0.0:9002
  Scoreboard: https://0.0.0.0:9002/v1/rps/scores
  Signing   : sigstore
============================================================

Commands:
  challenge <peer_url> <peer_spiffe_id>  — Start a match
  scores                                 — Show scoreboard
  quit / exit                            — Exit

rps>
```

### Try Challenge (Optional)

You can test challenging your teammate on the **same trust domain**:

```text
rps> challenge https://4.185.66.130:9002 spiffe://raghad.inter-cloud-thi.de/game-server-noah
Round 1 — choose (r)ock, (p)aper, (s)cissors: r
```

**Example (Raghad challenging Noah):**
```text
rps> challenge https://4.185.66.130:9002 spiffe://raghad.inter-cloud-thi.de/game-server-noah
```

> **Note:** This only works if both players are on the **same trust domain**.
> Challenging a peer on a *different* trust domain will fail with `UNKNOWN_CA` — federation is needed.

### View Scoreboard

```text
rps> scores
```

If ACME is configured (see Bonus section), the scoreboard is also publicly accessible:
```bash
curl https://raghad.inter-cloud-thi.de/v1/rps/scores | jq
```

**At this point show:**
- ✅ **Single trust domain** — SPIRE is running, game uses mTLS (7 pts)
- ✅ **Visible SPIFFE IDs** — identity in banner (5 pts)
- ✅ **Score tracking** — type `scores` to show the scoreboard (3 pts)

---

# Demo Phase 2: Federated Reconfiguration

This section shows the **live reconfiguration** from single-domain to federated cross-domain play.

Pick one of the three options to exchange bundles with a peer, then update
your workload entry and re-fetch certificates.

## Option A: Manual Bundle Exchange

### 1. Export your bundle and send it to the peer

```bash
cd ~/spire-1.13.3
sudo ./bin/spire-server bundle show -format spiffe > /tmp/my.bundle
cat /tmp/my.bundle   # send this JSON to the peer
```

### 2. Import the peer's bundle

```bash
cat <<'BUNDLE_EOF' | sudo ./bin/spire-server bundle set \
  -format spiffe -id spiffe://noah.inter-cloud-thi.de
<PASTE PEER'S FULL JSON BUNDLE HERE>
BUNDLE_EOF

sudo ./bin/spire-server bundle list
# Should list BOTH trust domains
```

## Option B: Bundle Endpoint (Automatic Fetch)

Both SPIRE servers expose their bundle on port **8443** (configured in server.conf).

```bash
cd ~/spire-1.13.3

# Fetch the peer's bundle directly
curl -sk https://4.185.66.130:8443 > /tmp/peer.bundle

# Import it
sudo ./bin/spire-server bundle set \
  -format spiffe \
  -id spiffe://noah.inter-cloud-thi.de \
  -path /tmp/peer.bundle

# Set up automatic refresh
sudo ./bin/spire-server federation create \
  -trustDomain noah.inter-cloud-thi.de \
  -bundleEndpointURL https://4.185.66.130:8443 \
  -bundleEndpointProfile https_spiffe \
  -endpointSpiffeID spiffe://noah.inter-cloud-thi.de/spire/server \
  -trustDomainBundlePath /tmp/peer.bundle \
  -trustDomainBundleFormat spiffe
```

> **NSG:** Ensure Azure NSG allows inbound TCP **8443** on both VMs.

## Option C: Fully Automated Script

If both sides have the bundle endpoint running:

```bash
chmod +x scripts/demo/setup-federation-auto.sh

# Federate with Raghad
./scripts/demo/setup-federation-auto.sh raghad.inter-cloud-thi.de 4.185.211.9

# Federate with Sven
./scripts/demo/setup-federation-auto.sh sven.inter-cloud-thi.de 4.185.210.163
```

The script auto-generates `~/spire.conf` if it doesn't exist (prompts for trust domain and player name), then fetches, imports, and creates the federation in one command.

## Re-register Workload WITH Federation

After importing the peer's bundle, delete the old entry and re-create with `-federatesWith`:

```bash
cd ~/spire-1.13.3

# Delete old entry
sudo ./bin/spire-server entry show
sudo ./bin/spire-server entry delete -entryID <OLD_ENTRY_ID>

# Re-create WITH federation
sudo ./bin/spire-server entry create \
  -spiffeID spiffe://raghad.inter-cloud-thi.de/game-server-raghad \
  -parentID spiffe://raghad.inter-cloud-thi.de/agent/myagent \
  -selector unix:uid:$(id -u) \
  -federatesWith spiffe://noah.inter-cloud-thi.de
```

> For multiple peers, add multiple `-federatesWith` flags:
> ```bash
> -federatesWith spiffe://raghad.inter-cloud-thi.de \
> -federatesWith spiffe://sven.inter-cloud-thi.de
> ```

## Re-fetch Certificates

Restart the agent so it picks up the new federated entry, then re-fetch:

```bash
cd ~/spire-1.13.3

sudo pkill -f spire-agent
sleep 3
sudo rm -rf /tmp/spire-agent/data/*
sudo rm -f /tmp/spire-agent/public/api.sock

TOKEN=$(sudo ./bin/spire-server token generate \
  -spiffeID spiffe://raghad.inter-cloud-thi.de/agent/myagent \
  | grep Token | awk '{print $2}')
sudo nohup ./bin/spire-agent run \
  -config /opt/spire/agent/agent.conf \
  -joinToken $TOKEN > /tmp/spire-agent.log 2>&1 &
sleep 30

sudo tail -20 /tmp/spire-agent.log

mkdir -p ~/certs && rm -f ~/certs/*
SPIFFE_ENDPOINT_SOCKET=/tmp/spire-agent/public/api.sock \
  ~/spire-1.13.3/bin/spire-agent api fetch x509 -write ~/certs/

ls ~/certs/
# Now you should see: svid.0.pem  svid.0.key  bundle.0.pem  federated_bundle.0.0.pem

# Combine ALL CAs into one bundle
cat ~/certs/bundle.0.pem ~/certs/federated_bundle.*.pem > ~/certs/svid_bundle.pem
mv ~/certs/svid.0.pem ~/certs/svid.pem
mv ~/certs/svid.0.key ~/certs/svid_key.pem

# Must show 2+ CAs (your own + each federated peer)
grep -c "BEGIN CERTIFICATE" ~/certs/svid_bundle.pem
```

## Restart Game & Play Cross-Domain

Restart the game (it loads certs once at startup):

```bash
./rps-game \
  --bind 0.0.0.0:9002 \
  --spiffe-id spiffe://raghad.inter-cloud-thi.de/game-server-raghad \
  --public-url https://4.185.211.9:9002 \
  --mtls --cert-dir ~/certs \
  --sign-moves
```

### Challenge Federated Peer

```text
rps> challenge https://4.185.66.130:9002 spiffe://noah.inter-cloud-thi.de/game-server-noah
Round 1 — choose (r)ock, (p)aper, (s)cissors: r
```

**Example (Raghad challenging Noah):**
```text
rps> challenge https://4.185.66.130:9002 spiffe://noah.inter-cloud-thi.de/game-server-noah
Round 1 — choose (r)ock, (p)aper, (s)cissors: r
```

### View Scoreboard

```text
rps> scores
```

If ACME is configured, the scoreboard is publicly accessible:
```bash
curl https://raghad.inter-cloud-thi.de/v1/rps/scores | jq
```

**Example (Raghad's public scoreboard):**
```bash
curl https://raghad.inter-cloud-thi.de/v1/rps/scores | jq
```

**At this point show:**
- ✅ **Federated reconfiguration** — bundle imported, entry updated, new certs fetched (7 pts)
- ✅ **Cross-domain authentication** — peer SPIFFE ID validated across trust domains (5 pts)
- ✅ **Move signing** — signed move shown in game output (4 pts bonus)

---

# Bonus: Move Signing (4 pts)

The `--sign-moves` flag enables cryptographic signing of each move during the reveal phase.
The game auto-detects the available signing method:

| Priority | Method | Tool | How it works |
|----------|--------|------|-------------|
| 1 | **Sigstore keyless** | `cosign` | OIDC identity → Fulcio certificate → Rekor transparency log |
| 2 | **SSH key** | `ssh-keygen` | Signs with `~/.ssh/id_ed25519` (no browser needed) |
| 3 | Unsigned | — | Fallback if neither tool is available |

### Binary

```bash
./rps-game --bind 0.0.0.0:9002 --mtls --cert-dir ~/certs \
  --spiffe-id spiffe://raghad.inter-cloud-thi.de/game-server-raghad \
  --public-url https://4.185.211.9:9002 \
  --sign-moves
```

### Docker

```bash
docker run -it --rm --network host \
  -v ~/certs:/app/certs:ro \
  -e RPS_SIGN_MOVES=1 \
  -e RPS_SPIFFE_ID=spiffe://raghad.inter-cloud-thi.de/game-server-raghad \
  -e RPS_PUBLIC_URL=https://4.185.211.9:9002 \
  -e RPS_MTLS=1 \
  ghcr.io/npaulat99/rock-paper-scissors:latest
```

### How it Works

1. When you reveal your move, the client signs the payload (`rps-v1|<match_id>|<round>|<move>|<salt>`)
2. The signature + method are included in the reveal HTTP request
3. The peer's server verifies the signature and shows the result:
   - `sigstore ✅ verified` — verified via Rekor transparency log
   - `ssh (signature received)` — SSH signature present
   - `unsigned` — no signature attached

---

# Bonus: ACME / Let's Encrypt Scoreboard (3 pts)

A **second HTTPS endpoint** using Let's Encrypt (WebPKI) certificates serves the scoreboard publicly. This demonstrates two distinct trust models running simultaneously:

- **Port 9002**: SPIFFE mTLS — client certificates required
- **Port 443**: WebPKI / ACME — standard server-only TLS, publicly accessible

## Obtain Certificate

```bash
sudo apt install -y certbot

# Standalone mode (stop anything on port 80 first)
sudo certbot certonly --standalone \
  -d raghad.inter-cloud-thi.de \
  --agree-tos --no-eff-email \
  -m raghad@thi.de

# Copy to user-readable location
mkdir -p ~/acme-certs
sudo cp /etc/letsencrypt/live/raghad.inter-cloud-thi.de/fullchain.pem ~/acme-certs/
sudo cp /etc/letsencrypt/live/raghad.inter-cloud-thi.de/privkey.pem ~/acme-certs/
sudo chown $USER:$USER ~/acme-certs/*.pem
```

## Run with ACME Scoreboard

### Binary (needs sudo for port 443)

```bash
sudo ./rps-game \
  --spiffe-id spiffe://raghad.inter-cloud-thi.de/game-server-raghad \
  --mtls --cert-dir ~/certs \
  --public-url https://4.185.211.9:9002 \
  --acme-cert ~/acme-certs/fullchain.pem \
  --acme-key ~/acme-certs/privkey.pem \
  --acme-bind 0.0.0.0:443 \
  --sign-moves
```

### Docker

```bash
docker run -it --rm --network host \
  -v ~/certs:/app/certs:ro \
  -v ~/acme-certs:/app/acme-certs:ro \
  -e RPS_BIND=0.0.0.0:9002 \
  -e RPS_SPIFFE_ID=spiffe://raghad.inter-cloud-thi.de/game-server-raghad \
  -e RPS_PUBLIC_URL=https://4.185.211.9:9002 \
  -e RPS_MTLS=1 \
  -e RPS_ACME_CERT=/app/acme-certs/fullchain.pem \
  -e RPS_ACME_KEY=/app/acme-certs/privkey.pem \
  -e RPS_ACME_BIND=0.0.0.0:443 \
  -e RPS_SIGN_MOVES=1 \
  ghcr.io/npaulat99/rock-paper-scissors:latest
```

Public scoreboard URL: `https://raghad.inter-cloud-thi.de/v1/rps/scores`

### ACME Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Connection refused` on port 443 | ACME not started | Pass `--acme-cert` and `--acme-key` flags |
| Not reachable externally | Azure NSG | Add inbound TCP 443 rule |
| `Permission denied` on port 443 | Privileged port | Use `sudo` or `--acme-bind 0.0.0.0:8444` |
| certbot fails | Port 80 in use or NSG closed | `sudo fuser -k 80/tcp` + open TCP 80 in NSG |

### Prerequisites

- **Azure NSG**: Inbound TCP **80** (certbot) and **443** (scoreboard)
- **DNS**: A-record for `raghad.inter-cloud-thi.de` pointing to `4.185.211.9`

---

# Troubleshooting

## "No identity issued" when fetching certs

The agent hasn't synced the workload entry yet. Restart with a new token:

```bash
cd ~/spire-1.13.3
sudo pkill -f spire-agent
sleep 3
sudo rm -rf /tmp/spire-agent/data/*
sudo rm -f /tmp/spire-agent/public/api.sock
TOKEN=$(sudo ./bin/spire-server token generate \
  -spiffeID spiffe://raghad.inter-cloud-thi.de/agent/myagent \
  | grep Token | awk '{print $2}')
sudo nohup ./bin/spire-agent run \
  -config /opt/spire/agent/agent.conf \
  -joinToken $TOKEN > /tmp/spire-agent.log 2>&1 &
sleep 30
sudo tail -20 /tmp/spire-agent.log
```

## "AlreadyExists" when creating entries

```bash
sudo ./bin/spire-server entry show   # Note the Entry ID
sudo ./bin/spire-server entry delete -entryID <THE_ID>
# Then re-create
```

## Timeout connecting to peer

1. Check peer's server: `sudo ss -tlnp | grep 9002`
2. Test TCP: `nc -zv -w 5 4.185.66.130 9002`
3. Open port 9002 TCP in **Azure NSG**
4. Local firewall: `sudo ufw allow 9002/tcp`

## SSL/TLS — "TLSV1_ALERT_UNKNOWN_CA"

The peer's cert was signed by a CA not in your `svid_bundle.pem`.
**Root cause:** SPIRE server was restarted → new CA key → old bundles invalid.

**Fix (both players):**

### 1. Re-exchange bundles with current CAs

```bash
# Export your fresh bundle
cd ~/spire-1.13.3
sudo ./bin/spire-server bundle show -format spiffe > /tmp/my.bundle
cat /tmp/my.bundle  # send to peer

# Import peer's fresh bundle
cat <<'BUNDLE_EOF' | sudo ./bin/spire-server bundle set \
  -format spiffe -id spiffe://noah.inter-cloud-thi.de
<PASTE FRESH BUNDLE HERE>
BUNDLE_EOF
```

### 2. Re-fetch certs on both VMs

```bash
cd ~/spire-1.13.3
sudo pkill -f spire-agent; sleep 3
sudo rm -rf /tmp/spire-agent/data/*
sudo rm -f /tmp/spire-agent/public/api.sock
TOKEN=$(sudo ./bin/spire-server token generate \
  -spiffeID spiffe://raghad.inter-cloud-thi.de/agent/myagent \
  | grep Token | awk '{print $2}')
sudo nohup ./bin/spire-agent run \
  -config /opt/spire/agent/agent.conf \
  -joinToken $TOKEN > /tmp/spire-agent.log 2>&1 &
sleep 30

mkdir -p ~/certs && rm -f ~/certs/*
SPIFFE_ENDPOINT_SOCKET=/tmp/spire-agent/public/api.sock \
  ~/spire-1.13.3/bin/spire-agent api fetch x509 -write ~/certs/

cat ~/certs/bundle.0.pem ~/certs/federated_bundle.*.pem > ~/certs/svid_bundle.pem
mv ~/certs/svid.0.pem ~/certs/svid.pem
mv ~/certs/svid.0.key ~/certs/svid_key.pem
grep -c "BEGIN CERTIFICATE" ~/certs/svid_bundle.pem  # Must be 2+
```

### 3. Restart the game on both VMs

The game loads certs at startup — you **must restart** after re-fetching.

## Expired SVID (certificates valid < 1 hour)

SVIDs expire after ~1 hour. Re-fetch certs (step 7) — no bundle re-exchange needed unless CA rotated.

## Delete old scoreboard entries

```bash
rm -f ~/.rps/scores.json
```

---

# Project Structure

```
rock-paper-scissors/
├── .github/workflows/
│   └── supply-chain.yml     # CI/CD pipeline with signing & attestations
├── attestations/            # SLSA provenance, SBOM, vulnerability reports
├── scripts/
│   ├── download-and-verify-binary.sh
│   ├── container/
│   │   └── entrypoint.sh    # Docker entrypoint
│   └── demo/
│       ├── common.sh        # Shared helpers, auto-generates ~/spire.conf
│       └── setup-federation-auto.sh  # One-command federation setup
├── src/
│   ├── app/
│   │   ├── cli.py           # Interactive CLI (serve + challenge in one process)
│   │   ├── commit_reveal.py # SHA256 commitment scheme
│   │   ├── http_api.py      # HTTP server with mTLS
│   │   ├── move_signing.py  # Sigstore / SSH move signing & verification
│   │   ├── protocol.py      # Game rules
│   │   ├── rps_client.py    # HTTP client for challenges
│   │   ├── scoreboard.py    # Score tracking per SPIFFE ID
│   │   └── spiffe_mtls.py   # SPIFFE mTLS SSL contexts
│   ├── docker/
│   │   └── Dockerfile
│   └── k8s/                 # Kubernetes manifests
└── tests/
    └── test_protocol.py
```

---

# Cleanup

```bash
sudo pkill -f spire-server
sudo pkill -f spire-agent
docker stop $(docker ps -q --filter ancestor=ghcr.io/npaulat99/rock-paper-scissors:latest) 2>/dev/null || true
sudo rm -rf /tmp/spire-server /tmp/spire-agent /tmp/bootstrap-bundle.crt
sudo rm -f /tmp/spire-server.log /tmp/spire-agent.log
```

