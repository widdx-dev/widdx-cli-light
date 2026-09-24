#!/usr/bin/env bash
# ===========================================================================
# WIDDX Nexus — SSL/TLS Auto Setup (Let's Encrypt + Certbot)
# ===========================================================================
# Usage:
#   export WIDDX_DOMAIN="widdx.yourdomain.com"
#   export WIDDX_EMAIL="admin@yourdomain.com"
#   bash deploy/ssl-setup.sh
# ===========================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

DOMAIN="${WIDDX_DOMAIN:-}"
EMAIL="${WIDDX_EMAIL:-}"
MODE="${1:-install}"

if [[ -z "$DOMAIN" ]]; then
    echo -e "${RED}❌ WIDDX_DOMAIN is not set${NC}"
    echo "   export WIDDX_DOMAIN='widdx.yourdomain.com'"
    exit 1
fi

echo -e "${GREEN}╔══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  WIDDX Nexus — SSL Auto Setup           ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════╝${NC}"
echo ""
echo "  Domain: $DOMAIN"
echo "  Email:  ${EMAIL:-"(will use --register-unsafely-without-email)"}"
echo "  Mode:   $MODE"
echo ""

case "$MODE" in
    install)
        echo -e "${YELLOW}→ Installing Certbot...${NC}"
        if command -v apt-get &> /dev/null; then
            sudo apt-get update
            sudo apt-get install -y certbot python3-certbot-nginx
        elif command -v yum &> /dev/null; then
            sudo yum install -y certbot python3-certbot-nginx
        elif command -v dnf &> /dev/null; then
            sudo dnf install -y certbot python3-certbot-nginx
        else
            echo -e "${RED}❌ Unsupported package manager${NC}"
            echo "   Please install certbot manually: https://certbot.eff.org/"
            exit 1
        fi

        echo -e "${YELLOW}→ Obtaining SSL certificate...${NC}"
        if [[ -n "$EMAIL" ]]; then
            sudo certbot --nginx \
                -d "$DOMAIN" \
                --non-interactive \
                --agree-tos \
                --email "$EMAIL"
        else
            sudo certbot --nginx \
                -d "$DOMAIN" \
                --non-interactive \
                --register-unsafely-without-email \
                --agree-tos
        fi

        echo -e "${GREEN}✅ SSL certificate installed for $DOMAIN${NC}"
        ;;

    renew)
        echo -e "${YELLOW}→ Renewing certificates...${NC}"
        sudo certbot renew --non-interactive
        sudo systemctl reload nginx
        echo -e "${GREEN}✅ Certificates renewed${NC}"
        ;;

    status)
        echo -e "${YELLOW}→ Certificate status:${NC}"
        sudo certbot certificates
        ;;

    auto-renew)
        echo -e "${YELLOW}→ Setting up auto-renewal...${NC}"
        # Certbot auto-renewal is set up by default via systemd timer
        echo "Check status: sudo systemctl status certbot.timer"
        echo "Test renewal: sudo certbot renew --dry-run"

        # Add to crontab as fallback
        (crontab -l 2>/dev/null || true; echo "0 3 * * * /usr/bin/certbot renew --quiet --post-hook 'systemctl reload nginx'") | crontab -
        echo -e "${GREEN}✅ Auto-renewal configured (daily at 3 AM)${NC}"
        ;;

    *)
        echo "Usage: $0 {install|renew|status|auto-renew}"
        echo ""
        echo "  install     — Install certbot + obtain certificate"
        echo "  renew       — Manually renew certificates"
        echo "  status      — Check certificate status"
        echo "  auto-renew  — Setup automatic renewal (cron + systemd)"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}✅ Done!${NC}"
echo "  Next: sudo systemctl reload nginx"
