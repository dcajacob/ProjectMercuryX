#!/usr/bin/env bash
# Install data only. All native executables and modules come from the build job.
set -euo pipefail
work=$(realpath "$1")
repo=$(realpath "$(dirname "$0")/../..")
cd "$work"
fetch() {
    curl --fail --location --silent --show-error --retry 3 "$1" -o "$2"
    printf '%s  %s\n' "$3" "$2" | sha256sum -c -
}
# This is the publisher's permanent redirect target for the original v3.1 download.
fetch https://cdn.orbithangar.com/user/a9748c7b-65fb-458a-898d-c3516a4fe691/addon/aa76f625-781d-4194-b153-16b81c9ae3e0/ProjectMercuryX-v3.1.zip \
    mercury.zip b35f077878c800ba49e6b4ab40a76544b190a754349166ee1ec7ec86b540cbc8
inputs=https://github.com/dcajacob/NASSP/releases/download/native-linux-ci-inputs-v1
fetch "$inputs/nassp-native-ci-inputs-v1.tar.zst" fixture.tar.zst 26d5891ea54a01ab8d007bed3ab2e9f5ed46ff8cd315921c57ca0e334faf37bd
tar --zstd --exclude='./runtime/engine' --exclude='./runtime/resources/Modules' --exclude='*ProjectApollo*' --exclude='*Apollo*' \
    -xf fixture.tar.zst ./runtime
rm fixture.tar.zst
# The template enables Apollo MFDs. Mercury uses the automatically loaded XRSound plug-in.
sed -i '/^ACTIVE_MODULES\r*$/,/^END_MODULES\r*$/d' runtime/Orbiter.cfg
fetch "$inputs/nassp-native-ci-terrain-v1.tar.zst" terrain.tar.zst 00e2e3d7198684a58ec4c96a148a485759d1695667e030416399a017dbe977db
tar --zstd -xf terrain.tar.zst -C runtime/planet-archives
rm terrain.tar.zst
fetch https://github.com/dcajacob/orbiter-cross-platform/releases/download/production-inputs-v2/production-stock-data-v1.zip \
    stock.zip b70a4065ceda469e4b0f35d3d8935138483873fdb8d8eb2dd6b99829f8ce0cb3
kernel=runtime/celestial-data/Kernels/orbiter.bsp
unzip -p stock.zip Kernels/orbiter.bsp > "$kernel"
printf '%s  %s\n' f98bd1a789fca05e0a1148db6d4b6d20ff7146896864bb04e4aac9c190371f83 "$kernel" | sha256sum -c -
rm stock.zip
python3 "$repo/Native/stage-assets.py" mercury.zip runtime
rm mercury.zip
