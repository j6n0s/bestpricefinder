# HTTPS for phones: Caddy in front of the app

`deploy/local/run-api.sh` serves the app on `http://127.0.0.1:8000`, reachable from this machine only. That is
enough on the Mac itself: browsers treat `http://127.0.0.1` as a secure context, so location works there.
A phone needs HTTPS, because browsers allow geolocation only in a secure context. [Caddy](https://caddyserver.com/)
terminates TLS and forwards the requests to the app. `Caddyfile.example` holds both options below and is checked
with `caddy validate` (Caddy 2.11).

| | (a) LAN, `tls internal` | (b) A real domain, Let's Encrypt |
|---|---|---|
| Who can reach it | Devices on your home network | Anyone on the internet who knows the name |
| Certificate | From Caddy's own local CA. You install its root certificate on the phone once | Automatic and publicly trusted |
| Needs | The Mac's LAN IP address (fix it with a DHCP reservation in the router) | A domain name, ports 80 and 443 forwarded to the Mac, a public IP |
| Env file | `BPF_TRUST_PROXY_HEADERS=true` | `BPF_TRUST_PROXY_HEADERS=true` and `BPF_HSTS=true` |
| Use it for | The founder's own phone. **Recommended.** | Only after the legal items below |

## What the Caddyfile does (both options)

- `reverse_proxy 127.0.0.1:8000`. The app keeps listening on localhost only.
- **Headers:** the app already sends its security headers: a `Content-Security-Policy` with the hashes of its
  inline scripts, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy` and so on (docs/API.md). Caddy
  passes them through unchanged and adds no security headers of its own, so nothing is duplicated or
  overridden. It only removes its own `Server` header.
- **HSTS** also comes from the app, with `BPF_HSTS=true`. Use it only with (b). With (a), a browser that
  received HSTS would refuse plain HTTP to that address for a year, and an IP address is not a stable
  identity.
- **Compression:** `encode zstd gzip`. The app has no cookies or secrets, so compression cannot leak any
  (BREACH).
- **Request body limit:** 64 KiB, the same as the app's own `BPF_API_MAX_BODY_BYTES`. Larger bodies get 413.
- **No access log.** It would record every visitor's IP address. A commented-out `log` block masks the
  addresses (IPv4 to /16, IPv6 to /32) and keeps 30 days, for debugging only.

After changing the env file, restart `deploy/local/run-api.sh`. `BPF_TRUST_PROXY_HEADERS=true` makes the app take
the client address from Caddy's `X-Forwarded-For`, so its per-IP rate limit sees the phone instead of Caddy.
That is safe because the app listens on 127.0.0.1 only: only local programs such as Caddy can send it the header.

## Install Caddy

- macOS: `brew install caddy`
- Debian/Ubuntu: see <https://caddyserver.com/docs/install#debian-ubuntu-raspbian>. Binding ports 80 and 443 as
  a normal user needs `sudo setcap cap_net_bind_service=+ep $(command -v caddy)` (option (b) only; (a) uses port
  8443).

## (a) LAN with Caddy's internal CA (recommended)

1. Find the Mac's LAN address: `ipconfig getifaddr en0` (Wi-Fi; Linux: `hostname -I`). Give it a fixed address
   in your router (a DHCP reservation), because the certificate is issued for that address.
2. In the env file (`.env.local`) add `BPF_TRUST_PROXY_HEADERS=true` and restart `deploy/local/run-api.sh`.
3. Start Caddy from the repository root, with your address:

   ```sh
   BPF_LAN_ADDRESS=192.168.1.20 caddy run --config deploy/local/caddy/Caddyfile.example --adapter caddyfile
   ```

   Caddy creates its local CA on the first start. macOS asks once whether `caddy` may accept incoming
   connections: allow it.
4. Copy the CA's **root certificate** (not the key) to the phone. It is in Caddy's data directory:
   - macOS: `~/Library/Application Support/Caddy/pki/authorities/local/root.crt`
   - Linux: `~/.local/share/caddy/pki/authorities/local/root.crt`

   Send it by AirDrop or e-mail, or put it on a USB stick.
5. Trust it on the phone:
   - **iPhone/iPad:** open the file, then Settings → *Profile Downloaded* → Install. Then Settings → General →
     About → Certificate Trust Settings → turn on full trust for "Caddy Local Authority".
   - **Android:** Settings → Security (and privacy) → More security settings → Encryption & credentials →
     Install a certificate → CA certificate. The menu names vary by vendor.
6. On the phone, open `https://192.168.1.20:8443`, allow location when the app explains why, and add it to the
   home screen.

Security notes:
- **Whoever has the CA's private key can impersonate any website to a phone that trusts the root.** The key is
  in the same `pki/authorities/local/` directory (`root.key`, mode 600). Never copy it anywhere. Install the
  root only on your own devices, and remove it (iPhone: Settings → General → VPN & Device Management) when you
  stop using this setup.
- `skip_install_trust` stops Caddy from adding its root to the Mac's own trust stores. The Mac does not need
  it, because it uses `http://127.0.0.1:8000` directly.
- Caddy renews the short-lived server certificates by itself. The root is valid for 10 years.
- Everyone on the same network can open the app. That is acceptable for public price data and our own
  recipes: nothing personal is stored on the server.

To keep Caddy running in the background on macOS, run `brew services start caddy` with the configuration
copied to Homebrew's Caddyfile (`$(brew --prefix)/etc/Caddyfile`, with your address instead of
`{$BPF_LAN_ADDRESS:...}`). Or simply run it in a terminal tab when you need it.

## (b) A real domain with Let's Encrypt

**This makes the app public.** Anyone who finds the name can use it, and that is a public release in the sense
of BUILD-BRIEF §8. Before doing it, the founder needs the impresszum, the privacy policy and the GVH re-use
permission (the request is drafted in `research/gap-gvh-reuse-legal-route/request_draft_hu.txt`). It also
exposes the Mac to the internet. For the founder's own use, prefer (a).

1. Point a DNS `A` (and `AAAA`) record for e.g. `bpf.example.org` at your public IP address, and forward
   TCP ports 80 and 443 from the router to the Mac.
2. Copy the example to `.data/caddy/Caddyfile` (git-ignored) and edit the copy:
   - delete `skip_install_trust` and `auto_https disable_redirects` from the global options (Caddy then
     redirects HTTP to HTTPS on port 80);
   - optionally set `email you@example.org`;
   - delete the (a) site block and uncomment the (b) one with your domain.
3. In the env file add `BPF_TRUST_PROXY_HEADERS=true` and `BPF_HSTS=true`, then restart `deploy/local/run-api.sh`.
   HSTS tells browsers to use only HTTPS for this name (and its subdomains) for a year.
4. `caddy run --config .data/caddy/Caddyfile --adapter caddyfile`. Caddy obtains and renews the certificate
   automatically.

## Checking a Caddyfile

```sh
caddy validate --config deploy/local/caddy/Caddyfile.example --adapter caddyfile
# or without installing Caddy:
docker run --rm -v "$PWD/deploy/local/caddy/Caddyfile.example:/etc/caddy/Caddyfile:ro" caddy:2-alpine \
  caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
```
