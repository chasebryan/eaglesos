#!/bin/bash

# Copyright 2024, UNSW
# SPDX-License-Identifier: BSD-2-Clause

#
# This script aims to build an already checked out version of EaglesOS.
#

set -e

if [ "$#" -ne 2 ]; then
    echo "usage: kitty.sh /path/to/eaglesos /path/to/microkit/sdk"
    exit 1
fi

LIONSOS=$1
MICROKIT_SDK=$2

build() {
    MICROKIT_BOARD=$1
    MICROKIT_CONFIG=debug

    echo "CI|INFO: building kitty for board: ${MICROKIT_BOARD}"

    BUILD_DIR="${LIONSOS}/ci_build/kitty/${MICROKIT_BOARD}/${MICROKIT_CONFIG}"
    rm -rf -- "$BUILD_DIR"

    export NFS_SERVER=0.0.0.0
    export NFS_DIRECTORY=test
    export BUILD_DIR MICROKIT_SDK MICROKIT_CONFIG MICROKIT_BOARD LIONSOS

    cd "$LIONSOS/examples/kitty"
    make
}

BOARDS=("odroidc4" "qemu_virt_aarch64")
for BOARD in "${BOARDS[@]}"
do
    build "$BOARD"
done

echo ""
echo "CI|INFO: completed all kitty builds"
