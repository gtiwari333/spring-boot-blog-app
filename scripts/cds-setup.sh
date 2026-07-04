#!/usr/bin/env bash
#
# CDS (Class Data Sharing) Archive Setup
# ========================================
# Creates and manages a CDS archive for fast application startup.
# The CDS archive pre-computes class metadata so the JVM skips
# class definition (defineClass1), ZIP decompression (Inflater),
# and classpath scanning — the top 3 CPU consumers identified in
# the JFR startup profile.
#
# Usage:
#   ./scripts/cds-setup.sh create    — Generate the CDS archive
#   ./scripts/cds-setup.sh run       — Start the app with CDS archive
#   ./scripts/cds-setup.sh clean     — Remove the CDS archive
#
# Prerequisites:
#   - Java 21+ with AppCDS support (included in all modern JDKs)
#   - Application JAR built via:  mvn -Pfast-startup package

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
JAR_FILE=$(ls "$PROJECT_DIR/target/"*-app.jar 2>/dev/null | head -1)
CDS_ARCHIVE="${CDS_ARCHIVE:-$PROJECT_DIR/target/application.jsa}"

# JVM options optimized for fast startup with CDS
FAST_STARTUP_OPTS=(
    "-XX:SharedArchiveFile=${CDS_ARCHIVE}"
    "-Dspring.aot.enabled=true"
    "-XX:TieredStopAtLevel=1"
    "-XX:InitialRAMPercentage=25.0"
    "-XX:MaxRAMPercentage=75.0"
    "-XX:+UseSerialGC"
)

die() {
    echo "[ERROR] $*" >&2
    exit 1
}

check_jar() {
    if [ -z "$JAR_FILE" ]; then
        die "No JAR found in target/. Build first: mvn -Pfast-startup package"
    fi
    echo "[INFO] Using JAR: $JAR_FILE"
}

cmd_create() {
    check_jar
    echo "[INFO] Creating CDS archive at: $CDS_ARCHIVE"
    echo "[INFO] This will start the app once to record loaded classes..."

    # Build JAR with AOT processing first
    echo "[INFO] Building with AOT processing..."
    (cd "$PROJECT_DIR" && mvn -Pfast-startup package -DskipTests -q) || die "Build failed"

    # Run once with ArchiveClassesAtExit to generate CDS
    echo "[INFO] Starting application to record class data (this will take ~20-30s)..."
    java \
        "-XX:ArchiveClassesAtExit=${CDS_ARCHIVE}" \
        "-Dspring.aot.enabled=true" \
        "-Dspring.main.lazy-initialization=true" \
        -jar "$JAR_FILE" &
    APP_PID=$!

    # Wait for the app to be ready, then shut down
    echo "[INFO] Waiting for application startup to complete..."
    for i in $(seq 1 60); do
        if curl -s http://localhost:8080/ >/dev/null 2>&1; then
            echo "[INFO] Application is ready. Stopping to finalize CDS archive..."
            kill "$APP_PID" 2>/dev/null || true
            wait "$APP_PID" 2>/dev/null || true
            break
        fi
        if ! kill -0 "$APP_PID" 2>/dev/null; then
            die "Application exited prematurely. Check logs."
        fi
        sleep 1
    done

    # Verify archive was created
    if [ -f "$CDS_ARCHIVE" ]; then
        ARCHIVE_SIZE=$(du -h "$CDS_ARCHIVE" | cut -f1)
        echo "[SUCCESS] CDS archive created: $CDS_ARCHIVE ($ARCHIVE_SIZE)"
        echo
        echo "To run with CDS:  ./scripts/cds-setup.sh run"
    else
        die "CDS archive was not created."
    fi
}

cmd_run() {
    check_jar
    if [ ! -f "$CDS_ARCHIVE" ]; then
        echo "[WARN] No CDS archive found. Run './scripts/cds-setup.sh create' first."
        echo "[INFO] Starting without CDS archive..."
        # Remove the SharedArchiveFile option
        OPTS=("${FAST_STARTUP_OPTS[@]:1}")
        java "${OPTS[@]}" -jar "$JAR_FILE"
    else
        echo "[INFO] Starting with CDS archive: $CDS_ARCHIVE"
        echo "[INFO] Expected startup: 5-8 seconds (vs 17s baseline)"
        java "${FAST_STARTUP_OPTS[@]}" -jar "$JAR_FILE"
    fi
}

cmd_clean() {
    if [ -f "$CDS_ARCHIVE" ]; then
        rm -f "$CDS_ARCHIVE"
        echo "[INFO] Removed CDS archive: $CDS_ARCHIVE"
    else
        echo "[INFO] No CDS archive to clean."
    fi
}

# --- Main ---
case "${1:-help}" in
    create) cmd_create ;;
    run)    cmd_run ;;
    clean)  cmd_clean ;;
    *)
        echo "Usage: $0 {create|run|clean}"
        echo
        echo "  create  — Build AOT-optimized JAR and generate CDS archive"
        echo "  run     — Start application with CDS archive (fastest startup)"
        echo "  clean   — Remove the CDS archive"
        echo
        echo "CDS archive location: $CDS_ARCHIVE"
        exit 1
        ;;
esac
