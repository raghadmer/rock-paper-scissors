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

# Setup Guide for Noah

**Trust Domain:** `noah.inter-cloud-thi.de`  
**Public IP:** `4.185.66.130`  
**SPIFFE ID:** `spiffe://noah.inter-cloud-thi.de/game-server-noah`  

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
  trust_domain = "noah.inter-cloud-thi.de"
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

## 3. Configure SPIRE Agent

```bash
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

## 4. Start SPIRE Server

```bash
cd ~/spire-1.13.3

# Kill any existing processes
sudo pkill -f spire-server || true
sudo pkill -f spire-agent || true
sleep 2

# Clean up
sudo rm -f /tmp/spire-server/private/api.sock
sudo rm -f /tmp/spire-agent/public/api.sock
sudo mkdir -p /tmp/spire-server/data
sudo mkdir -p /tmp/spire-agent/data /tmp/spire-agent/public

# Start server
sudo nohup ./bin/spire-server run -config /opt/spire/server/server.conf > /tmp/spire-server.log 2>&1 &
sleep 5

# Verify
sudo ./bin/spire-server healthcheck

# Save bootstrap bundle for agent
sudo ./bin/spire-server bundle show > /tmp/bootstrap-bundle.crt
```

## 5. Start SPIRE Agent

```bash
cd ~/spire-1.13.3

TOKEN=$(sudo ./bin/spire-server token generate \
  -spiffeID spiffe://noah.inter-cloud-thi.de/agent/myagent \
  | grep Token | awk '{print $2}')
echo "Token: $TOKEN"

sudo nohup ./bin/spire-agent run \
  -config /opt/spire/agent/agent.conf \
  -joinToken $TOKEN > /tmp/spire-agent.log 2>&1 &
sleep 5

# Verify
ls -la /tmp/spire-agent/public/api.sock
```

## 6. Export Your Trust Bundle & Import Raghad's Trust Bundle

> **IMPORTANT:** The peer's trust bundle must be imported **before** you can
> register a workload entry with `-federatesWith`. Otherwise SPIRE will
> reject the entry with *"unable to find federated bundle"*.

First, export your own bundle to share with Raghad:

```bash
cd ~/spire-1.13.3

# Export your trust bundle in SPIFFE format — send this to Raghad
sudo ./bin/spire-server bundle show -format spiffe
```

Copy the JSON output and send it to Raghad. Then import Raghad's trust
bundle by pasting the JSON she sends you:

```bash
cd ~/spire-1.13.3

cat <<'BUNDLE_EOF' | sudo ./bin/spire-server bundle set -format spiffe -id spiffe://raghad.inter-cloud-thi.de
<PASTE RAGHAD'S FULL JSON BUNDLE HERE>
BUNDLE_EOF

# Verify both bundles are listed
sudo ./bin/spire-server bundle list
# Should list: noah.inter-cloud-thi.de AND raghad.inter-cloud-thi.de
```

> **To get a fresh bundle from Raghad:** she runs
> `sudo ./bin/spire-server bundle show -format spiffe` and sends the output.

## 7. Register Workload with Federation

Now that Raghad's bundle is imported, you can create the workload entry
with `-federatesWith`.

First, clean up any stale entries from previous runs:

```bash
cd ~/spire-1.13.3

# Show all entries and delete any stale ones
sudo ./bin/spire-server entry show

# Delete each old entry (replace with actual IDs shown above)
# sudo ./bin/spire-server entry delete -entryID <ENTRY_ID>
# Repeat for every entry listed
```

Then create the workload entry:

```bash
sudo ./bin/spire-server entry create \
  -spiffeID spiffe://noah.inter-cloud-thi.de/game-server-noah \
  -parentID spiffe://noah.inter-cloud-thi.de/agent/myagent \
  -selector unix:uid:$(id -u) \
  -federatesWith spiffe://raghad.inter-cloud-thi.de

# Verify — should show FederatesWith: raghad.inter-cloud-thi.de
sudo ./bin/spire-server entry show
```

## 8. Fetch Certificates (with Combined Bundle)

After importing Raghad's bundle AND registering with `-federatesWith`,
restart the agent so it picks up the new entry, then fetch certs.

```bash
cd ~/spire-1.13.3

# Restart agent with a fresh join token
sudo pkill -f spire-agent
sleep 3
sudo rm -rf /tmp/spire-agent/data/*
sudo rm -f /tmp/spire-agent/public/api.sock
TOKEN=$(sudo ./bin/spire-server token generate \
  -spiffeID spiffe://noah.inter-cloud-thi.de/agent/myagent \
  | grep Token | awk '{print $2}')
sudo nohup ./bin/spire-agent run \
  -config /opt/spire/agent/agent.conf \
  -joinToken $TOKEN > /tmp/spire-agent.log 2>&1 &
sleep 30

# Verify agent picked up the entry — look for "Creating X509-SVID" for game-server-noah
sudo tail -20 /tmp/spire-agent.log

# Fetch certs
mkdir -p ~/certs
rm -f ~/certs/*
SPIFFE_ENDPOINT_SOCKET=/tmp/spire-agent/public/api.sock \
  ~/spire-1.13.3/bin/spire-agent api fetch x509 -write ~/certs/

# Verify the fetch succeeded — you must see these 4 files:
ls ~/certs/
# Expected: svid.0.pem  svid.0.key  bundle.0.pem  federated_bundle.0.0.pem
#
# If you see "no identity issued" or files are missing:
#   1. Check entry exists: sudo ./bin/spire-server entry show
#   2. Entry must have SPIFFE ID game-server-noah (not agent/myagent)
#   3. Entry selector must be unix:uid:$(id -u)
#   4. Restart agent again with a new token (repeat above)

# IMPORTANT: Combine both CAs into one bundle file
cat ~/certs/bundle.0.pem ~/certs/federated_bundle.0.0.pem > ~/certs/svid_bundle.pem
mv ~/certs/svid.0.pem ~/certs/svid.pem
mv ~/certs/svid.0.key ~/certs/svid_key.pem

# Verify 2 CAs in combined bundle
grep -c "BEGIN CERTIFICATE" ~/certs/svid_bundle.pem
# Must output: 2
```

## 9. Run the Game

### Option A: Using the signed binary

```bash
cd ~/temp
./rps-game \
  --bind 0.0.0.0:9002 \
  --spiffe-id spiffe://noah.inter-cloud-thi.de/game-server-noah \
  --public-url https://4.185.66.130:9002 \
  --mtls \
  --cert-dir ~/certs
```

### Option B: Using Docker

```bash
docker run -it --rm \
  --network host \
  -v ~/certs:/app/certs:ro \
  -e RPS_BIND=0.0.0.0:9002 \
  -e RPS_SPIFFE_ID=spiffe://noah.inter-cloud-thi.de/game-server-noah \
  -e RPS_PUBLIC_URL=https://4.185.66.130:9002 \
  -e RPS_MTLS=1 \
  ghcr.io/npaulat99/rock-paper-scissors:latest
```

You'll see an interactive prompt:

```text
============================================================
  Rock-Paper-Scissors — Interactive Mode
  SPIFFE ID : spiffe://noah.inter-cloud-thi.de/game-server-noah
  Listening : https://0.0.0.0:9002
  Scoreboard: https://0.0.0.0:9002/v1/rps/scores
============================================================

Commands:
  challenge <peer_url> <peer_spiffe_id>  — Start a match
  scores                                 — Show scoreboard
  quit / exit                            — Exit

rps>
```

### Challenge Raghad

```text
rps> challenge https://4.185.211.9:9002 spiffe://raghad.inter-cloud-thi.de/game-server-raghad
Round 1 — choose (r)ock, (p)aper, (s)cissors: s
Round 1: challenge sent, waiting for response...
```

### View Scores

```text
rps> scores
```

---

# Federating with Other Teams

To play against students **outside** your team (e.g., Sven), you have two
options for exchanging trust bundles. Both require updating your workload
entry to include `-federatesWith` for the new peer and re-fetching certs.

## Option A: Manual Bundle Exchange (`bundle set`)

No server config changes needed — just paste bundles back and forth.

### 1. Export your bundle and send it to the peer

```bash
cd ~/spire-1.13.3
sudo ./bin/spire-server bundle show -format spiffe > /tmp/noah.bundle
cat /tmp/noah.bundle   # send this JSON to the peer
```

**Command for the peer (e.g., Sven) to import your bundle:**

```bash
# Sven runs this on his VM:
cat <<'BUNDLE_EOF' | sudo /opt/spire/bin/spire-server bundle set \
  -format spiffe \
  -id spiffe://noah.inter-cloud-thi.de
<PASTE NOAH'S FULL JSON BUNDLE HERE>
BUNDLE_EOF
```

### 2. Import the peer's bundle

Ask the peer for their bundle output, then:

```bash
cd ~/spire-1.13.3

cat <<'BUNDLE_EOF' | sudo ./bin/spire-server bundle set -format spiffe -id spiffe://sven.inter-cloud-thi.de
<PASTE SVEN'S FULL JSON BUNDLE HERE>
BUNDLE_EOF

# Verify
sudo ./bin/spire-server bundle list
```

### 3. Update workload entry to federate with the new peer

```bash
cd ~/spire-1.13.3

# Delete old entry
sudo ./bin/spire-server entry show
sudo ./bin/spire-server entry delete -entryID <OLD_ENTRY_ID>

# Re-create with ALL peers listed
sudo ./bin/spire-server entry create \
  -spiffeID spiffe://noah.inter-cloud-thi.de/game-server-noah \
  -parentID spiffe://noah.inter-cloud-thi.de/agent/myagent \
  -selector unix:uid:$(id -u) \
  -federatesWith spiffe://raghad.inter-cloud-thi.de \
  -federatesWith spiffe://sven.inter-cloud-thi.de
```

### 4. Re-fetch certificates

```bash
cd ~/spire-1.13.3
sudo pkill -f spire-agent
sleep 3
sudo rm -rf /tmp/spire-agent/data/*
sudo rm -f /tmp/spire-agent/public/api.sock
TOKEN=$(sudo ./bin/spire-server token generate \
  -spiffeID spiffe://noah.inter-cloud-thi.de/agent/myagent \
  | grep Token | awk '{print $2}')
sudo nohup ./bin/spire-agent run \
  -config /opt/spire/agent/agent.conf \
  -joinToken $TOKEN > /tmp/spire-agent.log 2>&1 &
sleep 30

mkdir -p ~/certs && rm -f ~/certs/*
SPIFFE_ENDPOINT_SOCKET=/tmp/spire-agent/public/api.sock \
  ~/spire-1.13.3/bin/spire-agent api fetch x509 -write ~/certs/

# Combine ALL CA bundles (your own + all federated)
cat ~/certs/bundle.0.pem ~/certs/federated_bundle.*.pem > ~/certs/svid_bundle.pem
mv ~/certs/svid.0.pem ~/certs/svid.pem
mv ~/certs/svid.0.key ~/certs/svid_key.pem

# Verify — should show 1 + N (one per federated peer)
grep -c "BEGIN CERTIFICATE" ~/certs/svid_bundle.pem
```

### 5. Challenge the new peer

```text
rps> challenge https://4.185.210.163:9002 spiffe://sven.inter-cloud-thi.de/game-server-sven
```

## Option B: Automatic Bundle Endpoint (federation create)

This uses SPIRE's built-in bundle endpoint on port **8443** so peers can
automatically fetch your trust bundle over HTTPS. The `federation` block
is already included in the server.conf above.

### 1. Verify the bundle endpoint is running

After starting your SPIRE server, confirm port 8443 is listening:

```bash
sudo ss -tlnp | grep 8443
curl -k https://localhost:8443
```

> **NSG:** Make sure Azure NSG allows **inbound TCP 8443** on your VM.

### 2. Peer creates federation relationship

The peer (e.g., Sven) runs on their VM:

```bash
# First, delete any existing federation for this trust domain
sudo /opt/spire/bin/spire-server federation delete \
  -id spiffe://noah.inter-cloud-thi.de || true

# Create the federation relationship
sudo /opt/spire/bin/spire-server federation create \
  -trustDomain noah.inter-cloud-thi.de \
  -bundleEndpointURL https://4.185.66.130:8443 \
  -bundleEndpointProfile https_spiffe \
  -endpointSpiffeID spiffe://noah.inter-cloud-thi.de/game-server-noah \
  -trustDomainBundlePath /tmp/noah.bundle \
  -trustDomainBundleFormat spiffe
```

> **"UNIQUE constraint" error?** The peer already has a federation for
> your trust domain. They need to `federation delete` first (shown above),
> or use `federation update` instead of `federation create`.

### 3. You do the same for the peer

```bash
cd ~/spire-1.13.3

# Get the peer's bundle first
curl -k https://4.185.210.163:8443 > /tmp/sven.bundle

sudo ./bin/spire-server federation create \
  -trustDomain sven.inter-cloud-thi.de \
  -bundleEndpointURL https://4.185.210.163:8443 \
  -bundleEndpointProfile https_spiffe \
  -endpointSpiffeID spiffe://sven.inter-cloud-thi.de/game-server-sven \
  -trustDomainBundlePath /tmp/sven.bundle \
  -trustDomainBundleFormat spiffe
```

Then continue with steps 3–5 from Option A (update workload entry, re-fetch certs, challenge).

## Option C: Fully Automated Script

If both sides have the bundle endpoint running on port 8443, use the
automation script that fetches, imports, and creates the federation in
one command:

```bash
chmod +x scripts/demo/setup-federation-auto.sh

# Federate with Raghad
./scripts/demo/setup-federation-auto.sh raghad.inter-cloud-thi.de 4.185.211.9

# Federate with Sven
./scripts/demo/setup-federation-auto.sh sven.inter-cloud-thi.de 4.185.210.163
```

The script:
1. `curl -sk` fetches the peer's bundle from `https://PEER_IP:8443`
2. `spire-server bundle set` imports it
3. `spire-server federation create` sets up automatic background refresh

After running, update the workload entry (step 3) and re-fetch certs (step 4) as above.

> **First time?** Create `~/spire-lab.conf` from the example:
> ```bash
> cp scripts/demo/spire-lab.conf.example ~/spire-lab.conf
> nano ~/spire-lab.conf   # set your TRUST_DOMAIN
> ```

---

# Setup Guide for Raghad

**Trust Domain:** `raghad.inter-cloud-thi.de`  
**Public IP:** `4.185.211.9`  
**SPIFFE ID:** `spiffe://raghad.inter-cloud-thi.de/game-server-raghad`  

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

## 6. Export Your Trust Bundle & Import Noah's Trust Bundle

> **IMPORTANT:** The peer's trust bundle must be imported **before** you can
> register a workload entry with `-federatesWith`. Otherwise SPIRE will
> reject the entry with *"unable to find federated bundle"*.

First, export your own bundle to share with Noah:

```bash
cd ~/spire-1.13.3

# Export your trust bundle in SPIFFE format — send this to Noah
sudo ./bin/spire-server bundle show -format spiffe
```

Copy the JSON output and send it to Noah. Then import Noah's trust
bundle by pasting the JSON he sends you:

```bash
cd ~/spire-1.13.3

cat <<'BUNDLE_EOF' | sudo ./bin/spire-server bundle set -format spiffe -id spiffe://noah.inter-cloud-thi.de
<PASTE NOAH'S FULL JSON BUNDLE HERE>
BUNDLE_EOF

# Verify both bundles are listed
sudo ./bin/spire-server bundle list
# Should list: raghad.inter-cloud-thi.de AND noah.inter-cloud-thi.de
```

> **To get a fresh bundle from Noah:** he runs
> `sudo ./bin/spire-server bundle show -format spiffe` and sends the output.

## 7. Register Workload with Federation

Now that Noah's bundle is imported, you can create the workload entry
with `-federatesWith`.

First, clean up any stale entries from previous runs:

```bash
cd ~/spire-1.13.3

# Show all entries and delete any stale ones
sudo ./bin/spire-server entry show

# Delete each old entry (replace with actual IDs shown above)
# sudo ./bin/spire-server entry delete -entryID <ENTRY_ID>
# Repeat for every entry listed
```

Then create the workload entry:

```bash
sudo ./bin/spire-server entry create \
  -spiffeID spiffe://raghad.inter-cloud-thi.de/game-server-raghad \
  -parentID spiffe://raghad.inter-cloud-thi.de/agent/myagent \
  -selector unix:uid:$(id -u) \
  -federatesWith spiffe://noah.inter-cloud-thi.de

# Verify — should show FederatesWith: noah.inter-cloud-thi.de
sudo ./bin/spire-server entry show
```

## 8. Fetch Certificates (with Combined Bundle)

After importing Noah's bundle AND registering with `-federatesWith`,
restart the agent so it picks up the new entry, then fetch certs.

```bash
cd ~/spire-1.13.3

# Restart agent with a fresh join token
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

# Verify agent picked up the entry — look for "Creating X509-SVID" for game-server-raghad
sudo tail -20 /tmp/spire-agent.log

# Fetch certs
mkdir -p ~/certs
rm -f ~/certs/*
SPIFFE_ENDPOINT_SOCKET=/tmp/spire-agent/public/api.sock \
  ~/spire-1.13.3/bin/spire-agent api fetch x509 -write ~/certs/

# Verify the fetch succeeded — you must see these 4 files:
ls ~/certs/
# Expected: svid.0.pem  svid.0.key  bundle.0.pem  federated_bundle.0.0.pem
#
# If you see "no identity issued" or files are missing:
#   1. Check entry exists: sudo ./bin/spire-server entry show
#   2. Entry must have SPIFFE ID game-server-raghad (not agent/myagent)
#   3. Entry selector must be unix:uid:$(id -u)
#   4. Restart agent again with a new token (repeat above)

# IMPORTANT: Combine both CAs into one bundle file
cat ~/certs/bundle.0.pem ~/certs/federated_bundle.0.0.pem > ~/certs/svid_bundle.pem
mv ~/certs/svid.0.pem ~/certs/svid.pem
mv ~/certs/svid.0.key ~/certs/svid_key.pem

# Verify 2 CAs in combined bundle
grep -c "BEGIN CERTIFICATE" ~/certs/svid_bundle.pem
# Must output: 2
```

## 9. Run the Game

```bash
docker pull ghcr.io/npaulat99/rock-paper-scissors:latest

docker run -it --rm \
  --network host \
  -v ~/certs:/app/certs:ro \
  -e RPS_BIND=0.0.0.0:9002 \
  -e RPS_SPIFFE_ID=spiffe://raghad.inter-cloud-thi.de/game-server-raghad \
  -e RPS_PUBLIC_URL=https://4.185.211.9:9002 \
  -e RPS_MTLS=1 \
  ghcr.io/npaulat99/rock-paper-scissors:latest
```

### Challenge Noah

```
rps> challenge https://4.185.66.130:9002 spiffe://noah.inter-cloud-thi.de/game-server-noah
```

---

# ACME / Let's Encrypt Public Scoreboard (Bonus)

The game supports a **second HTTPS endpoint** for the scoreboard using **Let's Encrypt (WebPKI)** certificates, separate from the SPIFFE mTLS game port.

This demonstrates two distinct trust models running simultaneously:
- **Port 9002**: SPIFFE mTLS — client certificates required, peer identity validated via SPIFFE URI SANs
- **Port 443**: WebPKI / ACME — standard server-only TLS, publicly accessible scoreboard

## Obtain Let's Encrypt Certificate

On the Azure VM (requires DNS zone access — see ACME lab):

```bash
# Install certbot
sudo apt install -y certbot

# Use standalone mode (stop any service on port 80 first)
sudo certbot certonly --standalone \
  -d noah.inter-cloud-thi.de \
  --agree-tos --no-eff-email \
  -m noah@student.th-ingolstadt.de

# Certs are in /etc/letsencrypt/live/noah.inter-cloud-thi.de/
sudo ls /etc/letsencrypt/live/noah.inter-cloud-thi.de/
# fullchain.pem  privkey.pem
```

**Alternative — DNS-01 challenge (if port 80 is blocked):**
```bash
# Using Azure DNS plugin
sudo apt install -y python3-certbot-dns-azure
sudo certbot certonly --dns-azure \
  --dns-azure-config /etc/letsencrypt/azure.ini \
  -d noah.inter-cloud-thi.de \
  --agree-tos --no-eff-email \
  -m noah@student.th-ingolstadt.de
```

## Run with ACME Scoreboard

### Prerequisites

1. **Azure NSG**: Open inbound TCP **80** (certbot challenge) and **443** (HTTPS scoreboard).
2. **DNS**: An A-record for `noah.inter-cloud-thi.de` pointing to `4.185.66.130`.
3. **Stop anything on port 80** before running certbot (`sudo fuser -k 80/tcp`).

### Copy certs to user-readable location

```bash
mkdir -p ~/acme-certs
sudo cp /etc/letsencrypt/live/noah.inter-cloud-thi.de/fullchain.pem ~/acme-certs/
sudo cp /etc/letsencrypt/live/noah.inter-cloud-thi.de/privkey.pem ~/acme-certs/
sudo chown $USER:$USER ~/acme-certs/*.pem
```

### Option A: Binary (downloaded release)

Port 443 requires elevated privileges. Use `sudo`:

```bash
sudo ./rps-game \
  --spiffe-id spiffe://noah.inter-cloud-thi.de/game-server-noah \
  --mtls --cert-dir ~/certs \
  --public-url https://4.185.66.130:9002 \
  --acme-cert ~/acme-certs/fullchain.pem \
  --acme-key ~/acme-certs/privkey.pem \
  --acme-bind 0.0.0.0:443
```

### Option B: Docker container

```bash
docker run -it --rm \
  --network host \
  -v ~/certs:/app/certs:ro \
  -v ~/acme-certs:/app/acme-certs:ro \
  -e RPS_BIND=0.0.0.0:9002 \
  -e RPS_SPIFFE_ID=spiffe://noah.inter-cloud-thi.de/game-server-noah \
  -e RPS_PUBLIC_URL=https://4.185.66.130:9002 \
  -e RPS_MTLS=1 \
  -e RPS_ACME_CERT=/app/acme-certs/fullchain.pem \
  -e RPS_ACME_KEY=/app/acme-certs/privkey.pem \
  -e RPS_ACME_BIND=0.0.0.0:443 \
  ghcr.io/npaulat99/rock-paper-scissors:latest
```

The scoreboard is then publicly accessible at:
```
https://noah.inter-cloud-thi.de/v1/rps/scores
```

### ACME Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `curl: (7) Connection refused` on port 443 | ACME scoreboard never started | Did you pass `--acme-cert` and `--acme-key`? Without them the scoreboard is skipped. |
| Scoreboard starts but not reachable externally | Azure NSG blocks port 443 | Add inbound TCP 443 rule in Azure Portal. |
| `Permission denied` binding port 443 | Privileged port (<1024) | Use `sudo` or try `--acme-bind 0.0.0.0:8444` (then URL becomes `https://noah.inter-cloud-thi.de:8444/v1/rps/scores`). |
| certbot fails  | Port 80 occupied or NSG closed | `sudo fuser -k 80/tcp` and add inbound TCP 80 to NSG. |
| Browser shows "Not Secure" | Used Let's Encrypt staging | Re-run certbot **without** `--staging` flag. |

---

# Troubleshooting

## "No identity issued" when fetching certs

The SPIRE agent hasn't synced the workload entry. Fix:
```bash
cd ~/spire-1.13.3
sudo pkill -f spire-agent
sleep 3
sudo rm -rf /tmp/spire-agent/data/*
sudo rm -f /tmp/spire-agent/public/api.sock
TOKEN=$(sudo ./bin/spire-server token generate \
  -spiffeID spiffe://YOUR_DOMAIN/agent/myagent \
  | grep Token | awk '{print $2}')
sudo nohup ./bin/spire-agent run \
  -config /opt/spire/agent/agent.conf \
  -joinToken $TOKEN > /tmp/spire-agent.log 2>&1 &
sleep 30
sudo tail -20 /tmp/spire-agent.log
```

## "AlreadyExists" when creating entries

Delete the old entry first:
```bash
sudo ./bin/spire-server entry show   # Note the Entry ID
sudo ./bin/spire-server entry delete -entryID <THE_ID>
# Then re-create
```

## Timeout connecting to peer

1. Check the peer's server is running: `sudo ss -tlnp | grep 9002`
2. Test TCP connectivity: `nc -zv -w 5 <PEER_IP> 9002`
3. If blocked: open port 9002 TCP inbound in **Azure NSG** (Portal → VM → Networking)
4. Check local firewall: `sudo ufw allow 9002/tcp`

## SSL/TLS errors — "TLSV1_ALERT_UNKNOWN_CA"

This means the peer's certificate was signed by a CA that isn't in your `svid_bundle.pem`. 
**Root cause:** SPIRE server was restarted with a clean data directory → new CA key generated → old bundles no longer valid.

**Fix (both players must do this):**

### 1. Verify the CA mismatch

```bash
# Check YOUR current CA fingerprint
openssl x509 -in ~/certs/bundle.0.pem -noout -fingerprint -sha256

# Ask the peer to check THEIR CA fingerprint
# If they don't match what you exchanged earlier → re-exchange needed
```

### 2. Re-exchange bundles with CURRENT CAs

**Noah exports fresh bundle:**
```bash
cd ~/spire-1.13.3
sudo ./bin/spire-server bundle show -format spiffe > /tmp/noah.bundle
cat /tmp/noah.bundle  # send to Raghad
```

**Raghad imports Noah's fresh bundle:**
```bash
cd ~/spire-1.13.3
cat <<'BUNDLE_EOF' | sudo ./bin/spire-server bundle set -format spiffe -id spiffe://noah.inter-cloud-thi.de
<PASTE NOAH'S FRESH BUNDLE HERE>
BUNDLE_EOF
```

**Raghad exports her fresh bundle → Noah imports** (same steps, swapped).

### 3. Verify bundle list on BOTH VMs

```bash
sudo ./bin/spire-server bundle list
# Must show BOTH trust domains with current timestamps
```

### 4. Re-fetch certs on BOTH VMs

```bash
cd ~/spire-1.13.3
sudo pkill -f spire-agent
sleep 3
sudo rm -rf /tmp/spire-agent/data/*
sudo rm -f /tmp/spire-agent/public/api.sock
TOKEN=$(sudo ./bin/spire-server token generate \
  -spiffeID spiffe://noah.inter-cloud-thi.de/agent/myagent \
  | grep Token | awk '{print $2}')
sudo nohup ./bin/spire-agent run \
  -config /opt/spire/agent/agent.conf \
  -joinToken $TOKEN > /tmp/spire-agent.log 2>&1 &
sleep 30

mkdir -p ~/certs && rm -f ~/certs/*
SPIFFE_ENDPOINT_SOCKET=/tmp/spire-agent/public/api.sock \
  ~/spire-1.13.3/bin/spire-agent api fetch x509 -write ~/certs/

# Combine bundles
cat ~/certs/bundle.0.pem ~/certs/federated_bundle.*.pem > ~/certs/svid_bundle.pem
mv ~/certs/svid.0.pem ~/certs/svid.pem
mv ~/certs/svid.0.key ~/certs/svid_key.pem

# CRITICAL: Verify 2 CAs in the combined bundle
grep -c "BEGIN CERTIFICATE" ~/certs/svid_bundle.pem  # Must output: 2 (or more if federating with multiple peers)
```

### 5. RESTART the game on BOTH VMs

**CRITICAL:** The game loads certs once at startup. If you re-fetch while it's running, **you must restart**:

```bash
# Stop the running container
docker stop $(docker ps -q --filter ancestor=ghcr.io/npaulat99/rock-paper-scissors:latest)

# Or if using binary, Ctrl+C to stop, then re-run

# Start fresh with NEW certs
docker run -it --rm \
  --network host \
  -v ~/certs:/app/certs:ro \
  -e RPS_BIND=0.0.0.0:9002 \
  -e RPS_SPIFFE_ID=spiffe://noah.inter-cloud-thi.de/game-server-noah \
  -e RPS_PUBLIC_URL=https://4.185.66.130:9002 \
  -e RPS_MTLS=1 \
  ghcr.io/npaulat99/rock-paper-scissors:latest
```

### 6. Verify cert validity before playing

```bash
# Check your SVID expiration
openssl x509 -in ~/certs/svid.pem -noout -dates

# Check bundle has 2 CAs
openssl crl2pkcs7 -nocrl -certfile ~/certs/svid_bundle.pem | \
  openssl pkcs7 -print_certs -noout
# Should show Subject lines for BOTH noah and raghad CAs
```

Now try challenging again.

## Expired SVID (certificates valid < 1 hour)

SVIDs expire after 1 hour by default. Re-fetch from **Step 4** above (no bundle re-exchange needed unless CA rotated).

## Checking registered entries

```bash
sudo ./bin/spire-server entry show
# Verify:
# - SPIFFE ID matches what you pass to --spiffe-id
# - FederatesWith lists the peer's trust domain
# - Selector matches: unix:uid:<your-uid>
```

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
│   └── container/
│       └── entrypoint.sh    # Docker entrypoint
├── src/
│   ├── app/
│   │   ├── cli.py           # Interactive CLI (serve + challenge in one process)
│   │   ├── commit_reveal.py # SHA256 commitment scheme
│   │   ├── http_api.py      # HTTP server with mTLS
│   │   ├── move_signing.py  # Sigstore/SSH move signing
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
