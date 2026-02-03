# Domain & TLS Configuration for OrcaZap

## DNS Configuration

### Required DNS Records

All records point to the same VPS (VPS1):

1. **Apex domain (A record)**
   - Name: `orcazap.com`
   - Type: A
   - Value: `<VPS1_IP_ADDRESS>`
   - TTL: 3600

2. **WWW subdomain (CNAME)**
   - Name: `www.orcazap.com`
   - Type: CNAME
   - Value: `orcazap.com`
   - TTL: 3600

3. **API subdomain (A record)**
   - Name: `api.orcazap.com`
   - Type: A
   - Value: `<VPS1_IP_ADDRESS>`
   - TTL: 3600

4. **Wildcard subdomain (A record)**
   - Name: `*.orcazap.com`
   - Type: A
   - Value: `<VPS1_IP_ADDRESS>`
   - TTL: 3600

### DNS Provider Setup

The exact steps depend on your DNS provider. Common providers:

- **Cloudflare**: Add A records in DNS dashboard
- **Route53**: Create hosted zone and records
- **Namecheap**: Advanced DNS settings

**Important**: The wildcard record (`*.orcazap.com`) is critical for tenant subdomains to work automatically.

## TLS Certificate Setup

### Wildcard Certificate with Let's Encrypt (DNS-01 Challenge)

We use Certbot with DNS-01 challenge to obtain a wildcard certificate that covers:
- `orcazap.com`
- `www.orcazap.com`
- `api.orcazap.com`
- `*.orcazap.com`

### Prerequisites

1. Certbot installed: `apt install certbot python3-certbot-nginx`
2. DNS records configured (see above)
3. Nginx configured (see `infra/templates/nginx/orcazap.nginx.conf.tmpl`)

### Certificate Issuance

#### Option 1: Manual DNS Challenge (Recommended for wildcard)

```bash
# Request wildcard certificate with DNS-01 challenge
certbot certonly \
  --manual \
  --preferred-challenges dns \
  -d "*.orcazap.com" \
  -d "orcazap.com" \
  -d "www.orcazap.com" \
  -d "api.orcazap.com" \
  --email your-email@example.com \
  --agree-tos \
  --no-eff-email
```

Certbot will prompt you to add a TXT record to your DNS. Follow the instructions, then press Enter.

#### Option 2: Automated DNS Challenge (if using supported provider)

If your DNS provider supports Certbot plugins (e.g., Cloudflare, Route53):

```bash
# Install provider plugin (example for Cloudflare)
pip install certbot-dns-cloudflare

# Create credentials file
mkdir -p /etc/letsencrypt
cat > /etc/letsencrypt/cloudflare.ini <<EOF
dns_cloudflare_api_token = YOUR_CLOUDFLARE_API_TOKEN
EOF
chmod 600 /etc/letsencrypt/cloudflare.ini

# Request certificate
certbot certonly \
  --dns-cloudflare \
  --dns-cloudflare-credentials /etc/letsencrypt/cloudflare.ini \
  -d "*.orcazap.com" \
  -d "orcazap.com" \
  -d "www.orcazap.com" \
  -d "api.orcazap.com"
```

### Certificate Location

After issuance, certificates are stored at:
- Certificate: `/etc/letsencrypt/live/orcazap.com/fullchain.pem`
- Private Key: `/etc/letsencrypt/live/orcazap.com/privkey.pem`
- Chain: `/etc/letsencrypt/live/orcazap.com/chain.pem`

### Auto-renewal

Certbot sets up automatic renewal via systemd timer. Test renewal:

```bash
# Test renewal (dry run)
certbot renew --dry-run

# Manual renewal
certbot renew
```

### Nginx Configuration

The Nginx configuration template (`infra/templates/nginx/orcazap.nginx.conf.tmpl`) includes:

1. HTTP to HTTPS redirect
2. SSL certificate paths
3. SSL protocol and cipher configuration
4. Separate server blocks for:
   - Public site (apex + www)
   - API host
   - Tenant subdomains (wildcard)

### Deployment Steps

1. **Configure DNS records** (see above)
2. **Obtain certificate** (see above)
3. **Deploy Nginx config**:
   ```bash
   # Copy template and substitute variables
   envsubst < infra/templates/nginx/orcazap.nginx.conf.tmpl > /etc/nginx/sites-available/orcazap
   
   # Enable site
   ln -s /etc/nginx/sites-available/orcazap /etc/nginx/sites-enabled/
   
   # Test configuration
   nginx -t
   
   # Reload Nginx
   systemctl reload nginx
   ```

4. **Verify TLS**:
   - Visit `https://orcazap.com` - should show valid certificate
   - Visit `https://api.orcazap.com` - should show valid certificate
   - Visit `https://test.orcazap.com` (any tenant slug) - should show valid certificate

### Troubleshooting

**Certificate not issued:**
- Verify DNS records are propagated: `dig orcazap.com`
- Check DNS-01 challenge TXT record was added correctly
- Ensure port 80 is accessible for HTTP-01 (if using that method)

**Nginx SSL errors:**
- Verify certificate paths in config
- Check file permissions: `ls -la /etc/letsencrypt/live/orcazap.com/`
- Review Nginx error log: `tail -f /var/log/nginx/error.log`

**Wildcard not working:**
- Verify wildcard DNS record exists: `dig *.orcazap.com`
- Check certificate includes wildcard: `openssl x509 -in /etc/letsencrypt/live/orcazap.com/fullchain.pem -text -noout | grep DNS`

### Security Notes

1. **Certificate auto-renewal**: Ensure Certbot renewal timer is active
2. **Private key security**: Keep `/etc/letsencrypt/live/orcazap.com/privkey.pem` secure (600 permissions)
3. **HSTS**: Consider adding HSTS headers in Nginx config
4. **OCSP stapling**: Can be enabled in Nginx for better performance

### References

- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)
- [Certbot Documentation](https://certbot.eff.org/docs/)
- [Nginx SSL Configuration](https://nginx.org/en/docs/http/configuring_https_servers.html)





