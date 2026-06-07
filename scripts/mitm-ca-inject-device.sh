#!/system/bin/sh
# Inject mitmproxy CA into system + APEX conscrypt stores (zygote remount).
# Requires adb root. CACERT must already exist under /data/local/tmp/ (e.g. c8750f0d.0).

set -e

if [ -z "${CACERT}" ]; then
  echo "CACERT is not set" >&2
  exit 1
fi

if [ ! -f "/data/local/tmp/${CACERT}" ]; then
  echo "Missing /data/local/tmp/${CACERT} — push the mitmproxy CA first" >&2
  exit 1
fi

mkdir -p -m 700 /data/local/tmp/htk-ca-copy
cp /apex/com.android.conscrypt/cacerts/* /data/local/tmp/htk-ca-copy/
cp "/data/local/tmp/${CACERT}" /data/local/tmp/htk-ca-copy/

mv /data/local/tmp/htk-ca-copy/* /system/etc/security/cacerts/
chown root:root /system/etc/security/cacerts/*
chmod 644 /system/etc/security/cacerts/*
chcon u:object_r:system_file:s0 /system/etc/security/cacerts/*

echo 'Injecting certificates into APEX cacerts'
ZYGOTE_PID=$(pidof zygote || true)
ZYGOTE64_PID=$(pidof zygote64 || true)

if [ -z "$ZYGOTE_PID" ] && [ -z "$ZYGOTE64_PID" ]; then
  echo "No zygote or zygote64 process found — is the emulator fully booted?" >&2
  exit 1
fi

for Z_PID in $ZYGOTE_PID $ZYGOTE64_PID; do
  [ -n "$Z_PID" ] || continue
  nsenter --mount="/proc/${Z_PID}/ns/mnt" -- \
    mount --bind /system/etc/security/cacerts /apex/com.android.conscrypt/cacerts
done
echo 'Zygote APEX certificates remounted'

APP_PIDS=$(
  echo "$ZYGOTE_PID $ZYGOTE64_PID" | \
  xargs -n1 ps -o 'PID' -P | \
  grep -v PID
)

for PID in $APP_PIDS; do
  nsenter --mount="/proc/${PID}/ns/mnt" -- \
    mount --bind /system/etc/security/cacerts /apex/com.android.conscrypt/cacerts &
done
wait
echo "APEX certificates remounted for $(echo "$APP_PIDS" | wc -w) apps"

rm -rf /data/local/tmp/htk-ca-copy
