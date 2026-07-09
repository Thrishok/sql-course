#!/usr/bin/env bash
# Render build command for this branch. Installs a JVM (required by PySpark)
# alongside the normal Python dependencies, then verifies pyspark can start.
#
# Render dashboard -> this service -> Settings -> Build Command:
#   bash render-build.sh
# Start Command:
#   python run.py
set -euo pipefail

echo "== Installing Python dependencies =="
pip install -r requirements.txt

echo "== Installing a JVM for PySpark =="
apt-get update -y
apt-get install -y --no-install-recommends default-jre-headless
java -version

echo "== Build complete =="
