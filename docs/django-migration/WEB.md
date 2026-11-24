# Web deployment checkpoint

The experimental Compose now includes Django ASGI/Uvicorn and an unprivileged
nginx static/reverse proxy on loopback 18080. Static files are packaged locally;
no Node/npm build and no Django development server. Read-only services, bounded
tmpfs and distinct experiment image tags are retained. DB health endpoint returns
503 without exception details on failure. No proxy headers are trusted by Uvicorn.
TLS termination and trusted proxy configuration remain deployment responsibilities.

Set dedicated secrets and MICE_COOKIE_SECURE=false only for local plain HTTP;
the default is secure cookies. Set DJANGO_ALLOWED_HOSTS for the actual hostname.
Only implemented auth/users/operations pages are linked, not fake ports of the
remaining analyst interface. Static assets reuse legacy CSS; visual parity is
not yet validated. Image builds need registry access for the nginx base image.

No mail or benchmark validation is included. This checkpoint wires deployment,
not completion of the rest of the web migration.