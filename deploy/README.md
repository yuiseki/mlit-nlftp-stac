# Deploying the catalog

The catalog is a directory of static files. Anything that serves files over
HTTPS with CORS will do; what follows is how it is served from this machine,
which already runs nginx and a Cloudflare Tunnel.

The published location is `https://stac.yuiseki.net/mlit-nlftp/`, served from
`/data/www/html/stac/mlit-nlftp`. One host, one directory per catalog, so the
next catalog is a sibling directory rather than another hostname.

## 1. Build and stage

```bash
make build                    # BASE_URL defaults to the published location
make install-catalog          # rsync catalog/ -> /data/www/html/stac/mlit-nlftp
```

`install-catalog` uses `rsync --delete`, so a file that disappears upstream
stops being served rather than lingering.

`BASE_URL` only sets the absolute `self` links. Everything else stays
relative, so the same build still works from a local directory or under a
different prefix.

## 2. Serve it

```bash
sudo cp deploy/stac.yuiseki.net.conf /etc/nginx/sites-available/stac.yuiseki.net
sudo ln -s ../sites-available/stac.yuiseki.net /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
curl -s -H 'Host: stac.yuiseki.net' localhost/mlit-nlftp/catalog.json | head -c 120
```

The block listens on port 80 with a `server_name`, the same shape as the
`z.yuiseki.net` block already in `sites-available/default`. The tunnel passes
the Host header through and nginx dispatches on it, so another catalog host
needs no new port.

## 3. Publish the hostname

The tunnel on this machine runs from a token
(`/etc/systemd/system/cloudflared.service`), so its ingress rules live in the
Cloudflare dashboard rather than on disk. Add a public hostname there:

- Zero Trust → Networks → Tunnels → this tunnel → Public Hostnames → Add
- Hostname: `stac.yuiseki.net`
- Service: `HTTP` → `localhost:80`

## Why a path and not a subdomain per catalog

Cloudflare's Universal SSL covers the apex and **first-level subdomains only**
(<https://developers.cloudflare.com/ssl/>). `stac.yuiseki.net` is one level and
works with what is already there; `mlit-nlftp.stac.yuiseki.net` would be two
and would need Total TLS enabled on the zone.

## Size

About 94 MB in 21,714 files. That rules out Cloudflare Pages, which caps a
deployment at 20,000 files. R2 behind a Worker, or any plain static host, is
fine.
