"""Download the IBM Granite GGUF files that Docker Hub publishes as OCI model artifacts (no account, no key).
Usage: python scripts/pull_models.py OUT_DIR"""
import os, sys, requests

MODELS = {"granite-4.0-micro.gguf": "ai/granite-4.0-micro",
          "granite-embedding.gguf": "ai/granite-embedding-multilingual"}
ACCEPT = ("application/vnd.oci.image.manifest.v1+json,application/vnd.docker.distribution.manifest.v2+json,"
          "application/vnd.oci.image.index.v1+json")

def pull(repo, out):
    tok = requests.get("https://auth.docker.io/token", params={"service": "registry.docker.io",
                       "scope": f"repository:{repo}:pull"}, timeout=30).json()["token"]
    h = {"Authorization": f"Bearer {tok}", "Accept": ACCEPT}
    man = requests.get(f"https://registry-1.docker.io/v2/{repo}/manifests/latest", headers=h, timeout=30).json()
    digest = next(l["digest"] for l in man["layers"] if "gguf" in l["mediaType"])
    with requests.get(f"https://registry-1.docker.io/v2/{repo}/blobs/{digest}", headers=h, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(out + ".part", "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    os.replace(out + ".part", out)

if __name__ == "__main__":
    d = sys.argv[1]; os.makedirs(d, exist_ok=True)
    for name, repo in MODELS.items():
        p = os.path.join(d, name)
        if os.path.exists(p):
            print("have", name); continue
        print("pulling", repo); pull(repo, p); print("saved", p, os.path.getsize(p))
