# Edge front — nginx + SSH tunnels on one VPS

One VPS terminates TLS for every alias, so instances can bind localhost and still be reachable.

## Layout

```
/etc/nginx/conf.d/
  <group>.conf           443 <alias>.<ip>.nip.io → 127.0.0.1:<tunnel-port>
                         443 <alias>.<ip>.nip.io → <node>:<port>       (direct HTTP)
  upgrade.conf           map $http_upgrade $connection_upgrade
```

Certs under `/etc/letsencrypt/live/<group>/` with SANs for every alias in the group; auto-renew
via certbot webroot `/var/www/acme`.

Common server-block settings:

```nginx
proxy_http_version 1.1;
proxy_set_header Host $host;                 # required if the upstream routes on Host
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection $connection_upgrade;
proxy_buffering off;                         # SSE
proxy_read_timeout 3600s;
```

## systemd tunnels

```
[Unit]
Description=tunnel to <host>
After=network-online.target

[Service]
ExecStart=/usr/bin/ssh -N -L 127.0.0.1:<local>:<remote-host-or-ip>:<remote-port> \
  -i /root/.ssh/tunnel_key -p <ssh-port> -o ExitOnForwardFailure=yes \
  -o ServerAliveInterval=30 -o ServerAliveCountMax=3 root@<ssh-host>
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

- Use the **IP** in `-L`, not the hostname: per-channel DNS resolution adds ~0.8 s and can make
  the whole tunnel feel slow.
- `ExitOnForwardFailure=yes` + keepalives make a dead tunnel actually restart.
- If the egg host is far/slow from the edge, relay through a nearer host you already control and
  keep the direct hostname as the nginx backup upstream.

## New alias checklist

1. `tar -czf /root/nginx-backups/nginx-$(date -u +%Y%m%dT%H%M%SZ).tar.gz /etc/nginx`.
2. Add/extend the systemd tunnel; `systemctl daemon-reload && systemctl enable --now`.
3. Extend the cert SANs (`certbot certonly --webroot -w /var/www/acme -d <alias>…`).
4. Add the server block; `nginx -t && systemctl reload nginx`.
5. Verify: anon 401 on `/api/config`, auth 200, UI root 200, `time_total` < 0.3 s.

## Failure signatures

| Symptom | Meaning |
|---|---|
| 502 on one alias, 200 elsewhere | tunnel/systemd down or wrong upstream port |
| 421 from an upstream mux | Host not in its route list, or HTTP without the HTTPS gate header |
| 429 only via a provider alias | provider proxy rate limiting — your edge is the fix |
| ~1.7 s first byte on one group | nginx fell back to the slow direct upstream |
