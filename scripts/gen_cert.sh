#!/usr/bin/env bash
# モバイル等から HTTPS でカメラ(getUserMedia)を使うための自己署名証明書を生成する。
# localhost / 127.0.0.1 / 本機の LAN IP を SAN に含める。
set -euo pipefail
cd "$(dirname "$0")/.."

CERT_DIR="certs"
mkdir -p "$CERT_DIR"

LAN_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
LAN_IP="${LAN_IP:-127.0.0.1}"
SAN="DNS:localhost,IP:127.0.0.1,IP:${LAN_IP}"

echo "自己署名証明書を生成します (SAN: ${SAN})"
openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout "${CERT_DIR}/key.pem" -out "${CERT_DIR}/cert.pem" \
  -days 365 -subj "/CN=partmatch" -addext "subjectAltName=${SAN}" 2>/dev/null

echo "生成完了:"
echo "  ${CERT_DIR}/cert.pem"
echo "  ${CERT_DIR}/key.pem"
echo
echo "モバイルからのアクセス: https://${LAN_IP}:8443/ui/"
echo "（自己署名のため、初回はブラウザの警告を承認してください）"
