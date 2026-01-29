from __future__ import annotations

import os
import ssl
from dataclasses import dataclass


@dataclass(frozen=True)
class MtlsFiles:
    cert_path: str
    key_path: str
    bundle_path: str


def mtls_files_from_cert_dir(cert_dir: str) -> MtlsFiles:
    cert_path = os.path.join(cert_dir, "svid.pem")
    key_path = os.path.join(cert_dir, "svid_key.pem")
    bundle_path = os.path.join(cert_dir, "svid_bundle.pem")

    missing = [p for p in (cert_path, key_path, bundle_path) if not os.path.exists(p)]
    if missing:
        raise FileNotFoundError(
            "Missing SPIFFE mTLS file(s): "
            + ", ".join(missing)
            + " (expected svid.pem, svid_key.pem, svid_bundle.pem)"
        )

    return MtlsFiles(cert_path=cert_path, key_path=key_path, bundle_path=bundle_path)


def create_server_ssl_context(files: MtlsFiles) -> ssl.SSLContext:
    ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ctx.load_cert_chain(files.cert_path, files.key_path)
    ctx.load_verify_locations(files.bundle_path)
    ctx.verify_mode = ssl.CERT_REQUIRED
    # We authenticate peers via trust bundles + SPIFFE URI SAN (not DNS hostnames).
    ctx.check_hostname = False
    return ctx


def create_client_ssl_context(files: MtlsFiles) -> ssl.SSLContext:
    ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    ctx.load_cert_chain(files.cert_path, files.key_path)
    ctx.load_verify_locations(files.bundle_path)
    ctx.check_hostname = False
    return ctx


def extract_spiffe_id_from_peer_cert(ssl_sock: ssl.SSLSocket) -> str | None:
    # Python exposes SANs as ('URI', 'spiffe://...') tuples.
    cert = ssl_sock.getpeercert()
    if not cert:
        return None
    for san_type, san_value in cert.get("subjectAltName", ()):
        if san_type == "URI" and isinstance(san_value, str) and san_value.startswith("spiffe://"):
            return san_value
    return None
