# Deploying the catalog

The catalog is a directory of static files. Anything that serves files over
HTTPS with CORS will do; what follows is how it is served from this machine,
which already runs nginx and a Cloudflare Tunnel.

## 1. Build and stage

```bash
make build
sudo make install-catalog     # rsync catalog/ -> /srv/mlit-nlftp-stac
```

`install-catalog` uses `rsync --delete`, so a file removed upstream stops
being served rather than lingering.

## 2. Serve it

```bash
sudo cp deploy/nginx-mlit-nlftp-stac.conf /etc/nginx/sites-available/
sudo ln -s ../sites-available/nginx-mlit-nlftp-stac.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
curl -s localhost:8088/catalog.json | head -c 120
```

## 3. Publish the hostname

The tunnel on this machine runs from a token
(`/etc/systemd/system/cloudflared.service`), which means its ingress rules
live in the Cloudflare dashboard, not on disk. Add a public hostname there:

- Zero Trust → Networks → Tunnels → this tunnel → Public Hostnames → Add
- Hostname: the chosen name under `yuiseki.net`
- Service: `HTTP` → `localhost:8088`

## A note on the hostname

Cloudflare's Universal SSL covers the apex and **first-level subdomains only**
(<https://developers.cloudflare.com/ssl/>). `mlit-nlftp.stac.yuiseki.net` is
two levels deep, so it needs Total TLS enabled on the zone; without it the
name resolves but TLS fails. `mlit-nlftp-stac.yuiseki.net` is one level and
works with what is already there.

## Size

About 94 MB in 21,714 files. That rules out Cloudflare Pages, which caps a
deployment at 20,000 files. R2 behind a Worker, or any plain static host, is
fine.
