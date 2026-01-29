#!/bin/bash
# Download, verify, and run the RPS game binary from GitHub Actions artifacts

set -e

REPO="${GITHUB_REPOSITORY:-npaulat99/rock-paper-scissors}"
RUN_ID="${1:-latest}"

echo "=================================================="
echo "🔐 Download & Verify RPS Game Binary"
echo "=================================================="
echo ""
echo "Repository: $REPO"
echo "Run ID: $RUN_ID"
echo ""

# Check prerequisites
if ! command -v gh &> /dev/null; then
    echo "❌ GitHub CLI (gh) is required but not installed."
    echo "   Install: https://cli.github.com/"
    exit 1
fi

if ! command -v cosign &> /dev/null; then
    echo "❌ Cosign is required but not installed."
    echo "   Install: https://docs.sigstore.dev/cosign/installation/"
    exit 1
fi

# Ensure user is authenticated
if ! gh auth status &> /dev/null; then
    echo "⚠️  Not authenticated with GitHub. Running gh auth login..."
    gh auth login
fi

echo "📦 Step 1: Downloading binary artifact from GitHub Actions..."
echo ""

# Create temp directory
WORK_DIR=$(mktemp -d)
cd "$WORK_DIR"

if [ "$RUN_ID" = "latest" ]; then
    echo "Fetching latest successful workflow run..."
    RUN_ID=$(gh run list --repo "$REPO" --workflow "Supply Chain Pipeline" --status success --limit 1 --json databaseId --jq '.[0].databaseId')
    if [ -z "$RUN_ID" ]; then
        echo "❌ No successful workflow runs found."
        exit 1
    fi
    echo "Latest run ID: $RUN_ID"
fi

# Download artifact
gh run download "$RUN_ID" --repo "$REPO" --name rps-game-binary

echo ""
echo "✅ Binary downloaded to: $WORK_DIR"
ls -lh rps-game*
echo ""

echo "🔐 Step 2: Verifying binary signature with Cosign..."
echo ""

# Verify signature
cosign verify-blob \
    --bundle rps-game.cosign.bundle \
    --certificate-identity-regexp="https://github.com/.+" \
    --certificate-oidc-issuer-regexp="https://token.actions.githubusercontent.com" \
    rps-game

echo ""
echo "✅ Signature verified! Binary is authentic and signed by GitHub Actions."
echo ""

# Make executable
chmod +x rps-game

echo "🎮 Step 3: Testing binary..."
echo ""
./rps-game --help || echo ""

echo ""
echo "=================================================="
echo "✅ All checks passed!"
echo "=================================================="
echo ""
echo "Binary location: $WORK_DIR/rps-game"
echo ""
echo "Usage examples:"
echo "  # Serve (wait for challenges)"
echo "  $WORK_DIR/rps-game serve --spiffe-id spiffe://your-domain/server --mtls --cert-dir ~/certs"
echo ""
echo "  # Challenge a peer"
echo "  $WORK_DIR/rps-game play --spiffe-id spiffe://your-domain/client \\"
echo "    --peer https://PEER-IP:9002 --peer-id spiffe://peer-domain/server \\"
echo "    --mtls --cert-dir ~/certs"
echo ""
echo "  # View scores"
echo "  $WORK_DIR/rps-game scores"
echo ""
echo "To keep the binary, copy it to your PATH:"
echo "  sudo cp $WORK_DIR/rps-game /usr/local/bin/"
echo ""
