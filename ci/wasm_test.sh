#!/bin/bash

# Copyright 2026, UNSW
# SPDX-License-Identifier: BSD-2-Clause

#
# This script aims to build an already checked out version of EaglesOS.
#

set -e

if [ "$#" -ne 2 ]; then
    echo "usage: wasm_test.sh /path/to/eaglesos /path/to/microkit/sdk"
    exit 1
fi

LIONSOS=$1
MICROKIT_SDK=$2

build() {
    MICROKIT_BOARD=$1
    MICROKIT_CONFIG=debug

    echo "CI|INFO: building wasm_test for board: ${MICROKIT_BOARD}"

    BUILD_DIR="${LIONSOS}/ci_build/wasm_test/${MICROKIT_BOARD}/${MICROKIT_CONFIG}"
    rm -rf -- "$BUILD_DIR"

    export BUILD_DIR MICROKIT_SDK MICROKIT_CONFIG MICROKIT_BOARD LIONSOS

    cd "$LIONSOS/examples/wasm_test"
    make
}

BOARDS=("qemu_virt_aarch64")
for BOARD in "${BOARDS[@]}"
do
    build "$BOARD"
done

echo ""
echo "CI|INFO: completed all wasm_test builds"
