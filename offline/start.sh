#!/bin/sh
. "$(dirname "$0")/common.sh"
dc up -d --no-build --pull never --wait --wait-timeout 360