# Domain Setup Guide — gizmohub.ai

This guide covers everything needed to make Gizmo MY-AI publicly accessible at
`https://gizmohub.ai` from your Fedora home server.

---

## 1. DNS — Point your domain to your home IP

1. Log in to your DNS registrar (e.g. [Cloudflare](https://cloudflare.com)).
2. Add an **A record**:
   - Name: `@` (or `gizmohub.ai`)
   - Content: your home public IP address
   - TTL: Auto (or 1 min for quick updates)
3. Add a **CNAME** for `www`:
   - Name: `www`
   - Content: `gizmohub.ai`

> **Tip:** Use Cloudflare's **proxied** mode (orange cloud) for DDoS protection
> and to hide your home IP.

---

## 2. Dynamic IP — ddclient or Cloudflare DDNS

Most home connections have a dynamic IP.  Use **ddclient** to auto-update DNS:

```bash
sudo dnf install ddclient
sudo nano /etc/ddclient.conf
```

Example Cloudflare config:

```ini
protocol=cloudflare
zone=gizmohub.ai
login=your@email.com
password=your-cloudflare-api-token
ttl=1
gizmohub.ai
```

Enable and start:

```bash
sudo systemctl enable --now ddclient
```

---

## 3. Router Port Forwarding

Forward port **443** (HTTPS) from your router to your Fedora PC's local IP.

Example (router admin panel, varies by model):

| External Port | Protocol | Internal IP     | Internal Port |
|---|---|---|---|
| 443           | TCP      | 192.168.1.xxx   | 443           |

> Port 80 can also be forwarded if you want HTTP→HTTPS redirect via Caddy.

---

## 4. Fedora Firewall Rules

Allow HTTPS through the Fedora firewall:

```bash
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --reload
```

**Block direct access to port 7860** (Gradio should only be reachable via Caddy):

```bash
sudo firewall-cmd --permanent --add-rich-rule='rule port port="7860" protocol="tcp" reject'
sudo firewall-cmd --reload
```

---

## 5. Install Caddy (Reverse Proxy + Auto HTTPS)

```bash
sudo dnf install caddy
```

---

## 6. Caddy Configuration

Edit `/etc/caddy/Caddyfile`:

```caddyfile
gizmohub.ai {
    # Reverse proxy to Gradio
    reverse_proxy localhost:7860

    # Security headers
    header {
        X-Frame-Options SAMEORIGIN
        X-Content-Type-Options nosniff
        Referrer-Policy strict-origin-when-cross-origin
        Permissions-Policy "camera=(), microphone=(), geolocation=()"
        -Server
    }

    # Logging
    log {
        output file /var/log/caddy/gizmohub.log
        format json
    }
}

# Optional: redirect www → root
www.gizmohub.ai {
    redir https://gizmohub.ai{uri} permanent
}
```

Caddy automatically obtains and renews Let's Encrypt TLS certificates.

Enable and start:

```bash
sudo systemctl enable --now caddy
sudo systemctl status caddy
```

---

## 7. Systemd Service for Gizmo (Auto-Start on Boot)

Create `/etc/systemd/system/gizmo.service`:

```ini
[Unit]
Description=Gizmo MY-AI Self-Hosted Server
After=network.target

[Service]
Type=simple
User=leon
WorkingDirectory=/home/leon/projects/Gizmo
ExecStart=/home/leon/projects/Gizmo/start_fedora.sh
Restart=on-failure
RestartSec=10
EnvironmentFile=-/home/leon/projects/Gizmo/user_data/google_oauth.env
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Enable:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now gizmo
sudo journalctl -fu gizmo   # follow logs
```

---

## 8. Google OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (e.g. "Gizmo MY-AI").
3. Navigate to **APIs & Services → Credentials**.
4. Click **Create Credentials → OAuth 2.0 Client IDs**.
5. Application type: **Web application**.
6. Authorized JavaScript origins: `https://gizmohub.ai`
7. Authorized redirect URIs: `https://gizmohub.ai/oauth/callback`
8. Copy **Client ID** and **Client Secret** into `user_data/google_oauth.env`:

```bash
export GOOGLE_CLIENT_ID="your-client-id.apps.googleusercontent.com"
export GOOGLE_CLIENT_SECRET="your-secret"
export GIZMO_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
```

9. Add your Gmail address to `user_data/allowed_emails.txt` (first line = owner).

---

## 9. Verify Everything Works

```bash
# Check Caddy is running
sudo systemctl status caddy

# Check Gizmo is running
sudo systemctl status gizmo

# Check HTTPS certificate
curl -I https://gizmohub.ai

# Check firewall
sudo firewall-cmd --list-all
```

You should be able to visit `https://gizmohub.ai` and see the Google Sign-In page.
