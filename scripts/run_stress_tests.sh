#!/usr/bin/env bash
# ===========================================================================
#  WIDDX Nexus — Comprehensive Stress & Load Testing Runner
# ===========================================================================
#  Usage:
#    bash scripts/run_stress_tests.sh                  # Run all stress tests
#    bash scripts/run_stress_tests.sh quick             # Quick smoke test
#    bash scripts/run_stress_tests.sh full              # Full stress suite
#    bash scripts/run_stress_tests.sh locust            # Launch Locust web UI
#    bash scripts/run_stress_tests.sh locust-headless   # Headless Locust
# ===========================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

API_KEY="${WIDDX_API_KEY:-stress-test-key-007}"
export WIDDX_API_KEY="$API_KEY"

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════╗"
echo "║     WIDDX Nexus — Stress & Load Test Runner         ║"
echo "╚══════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Ensure dependencies are installed
echo -e "${YELLOW}→ Checking dependencies...${NC}"
python3 -c "import fastapi, uvicorn, httpx, pytest" 2>/dev/null || {
    echo -e "${YELLOW}  Installing missing dependencies...${NC}"
    pip install --break-system-packages fastapi uvicorn httpx pytest
}

MODE="${1:-quick}"

case "$MODE" in
    quick)
        echo -e "\n${GREEN}▶ Running QUICK stress smoke test...${NC}"
        echo -e "${YELLOW}  (Sections 1-3, small iteration counts)${NC}\n"
        WIDDX_API_KEY="$API_KEY" python -m pytest tests/test_stress_load.py \
            -v --tb=short -x \
            -k "sequential_burst_50 or round_robin or rate_limit_exceeded or missing_auth or invalid_auth or rate_limiter_high_throughput" \
            2>&1 | tail -40
        ;;

    full)
        echo -e "\n${GREEN}▶ Running FULL stress test suite...${NC}"
        echo -e "${YELLOW}  (All sections, may take several minutes)${NC}\n"
        WIDDX_API_KEY="$API_KEY" python -m pytest tests/test_stress_load.py \
            -v --tb=long \
            --timeout=300 \
            2>&1
        ;;

    locust)
        echo -e "\n${GREEN}▶ Launching Locust Web UI...${NC}"
        echo -e "${YELLOW}  Open http://localhost:8089 in your browser${NC}"
        echo -e "${YELLOW}  Point it at the running WIDDX API server${NC}\n"
        locust -f locustfile.py --web-port 8089
        ;;

    locust-headless)
        USERS="${LOCUST_USERS:-50}"
        RATE="${LOCUST_RATE:-10}"
        TIME="${LOCUST_TIME:-60s}"
        HOST="${LOCUST_HOST:-http://127.0.0.1:8000}"

        echo -e "\n${GREEN}▶ Running Locust headless...${NC}"
        echo -e "  Users: ${YELLOW}$USERS${NC}"
        echo -e "  Spawn Rate: ${YELLOW}$RATE/s${NC}"
        echo -e "  Duration: ${YELLOW}$TIME${NC}"
        echo -e "  Host: ${YELLOW}$HOST${NC}\n"
        locust -f locustfile.py --host="$HOST" \
            --headless --users "$USERS" --spawn-rate "$RATE" --run-time "$TIME"
        ;;

    ultra)
        USERS="${LOCUST_USERS:-200}"
        RATE="${LOCUST_RATE:-50}"
        TIME="${LOCUST_TIME:-120s}"
        HOST="${LOCUST_HOST:-http://127.0.0.1:8000}"

        echo -e "\n${RED}▶ ULTRA stress test — 200 users, 50/s spawn rate${NC}"
        locust -f locustfile.py --host="$HOST" \
            --headless --users "$USERS" --spawn-rate "$RATE" --run-time "$TIME" \
            --csv=reports/stress_report --html=reports/stress_report.html
        echo -e "\n${GREEN}  Report saved to reports/stress_report.html${NC}"
        ;;

    *)
        echo -e "${RED}Unknown mode: $MODE${NC}"
        echo "Usage: $0 {quick|full|locust|locust-headless|ultra}"
        exit 1
        ;;
esac

echo -e "\n${GREEN}✓ Stress test completed.${NC}"
