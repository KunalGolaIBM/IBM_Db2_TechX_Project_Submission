title: Automatic runtime installation fails because package or download endpoints are unreachable
category: RUNTIME_INSTALL
url: https://ibm.github.io/db2developerextension-about/

When the extension finds no Podman or Docker, it may try to install one automatically. That step needs outbound access to the distribution package mirrors (for Ubuntu: archive.ubuntu.com and security.ubuntu.com) and, for the Docker fallback, download.docker.com over HTTPS.
Typical log symptoms: "No container runtimes found", apt "Could not connect" or "Failed to fetch", "E: Unable to locate package podman", curl exit code 28 (timeout) or 6 (DNS), then a final "All runtime installations failed".
What to check from the same WSL terminal: whether `curl -I https://download.docker.com` and `sudo apt-get update` succeed; whether a campus or corporate proxy or VPN is required; whether HTTP_PROXY / HTTPS_PROXY are exported inside WSL (Windows proxy settings are not inherited automatically); DNS in /etc/resolv.conf.
Recovery path: install a supported runtime manually (e.g. `sudo apt-get install podman` once the network works, or enable Docker Desktop WSL integration), then reload VS Code so detection runs again.
Evidence boundary: network errors during installation show the endpoints were unreachable from that environment; they do not prove whether the cause is the extension, the proxy, DNS, or the mirror itself.
