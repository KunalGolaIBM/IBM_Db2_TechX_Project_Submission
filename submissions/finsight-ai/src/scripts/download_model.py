import os
import sys
import time
import requests
from concurrent.futures import ThreadPoolExecutor

URL = "https://huggingface.co/Qdrant/bge-small-en-v1.5-onnx-Q/resolve/main/model_optimized.onnx"
DEST = os.path.join(os.path.dirname(__file__), "model_optimized.onnx")
NUM_CHUNKS = 8

def download_chunk(args):
    idx, start, end, real_url = args
    headers = {"Range": f"bytes={start}-{end}"}
    for attempt in range(5):
        try:
            res = requests.get(real_url, headers=headers, timeout=60)
            if res.status_code in (200, 206):
                return idx, start, res.content
        except Exception as e:
            time.sleep(1)
    raise RuntimeError(f"Failed chunk {idx}")

def main():
    print("Resolving final URL...")
    head_res = requests.head(URL, allow_redirects=True, timeout=30)
    total_size = int(head_res.headers.get("content-length", 0))
    real_url = head_res.url
    print(f"Total size: {total_size:,} bytes ({total_size / (1024*1024):.2f} MB)")

    chunk_size = total_size // NUM_CHUNKS
    tasks = []
    for i in range(NUM_CHUNKS):
        start = i * chunk_size
        end = total_size - 1 if i == NUM_CHUNKS - 1 else (start + chunk_size - 1)
        tasks.append((i, start, end, real_url))

    print(f"Downloading with {NUM_CHUNKS} parallel streams...")
    t0 = time.time()
    results = {}
    with ThreadPoolExecutor(max_workers=NUM_CHUNKS) as pool:
        for idx, start, content in pool.map(download_chunk, tasks):
            results[idx] = content
            print(f" Chunk {idx+1}/{NUM_CHUNKS} complete ({len(content):,} bytes)")

    print(f"Assembling file -> {DEST}...")
    with open(DEST, "wb") as f:
        for i in range(NUM_CHUNKS):
            f.write(results[i])

    elapsed = time.time() - t0
    final_size = os.path.getsize(DEST)
    print(f"Done! Saved {final_size:,} bytes in {elapsed:.2f}s ({final_size / (1024*1024) / elapsed:.2f} MB/s).")
    assert final_size == total_size, f"Size mismatch: {final_size} != {total_size}"

if __name__ == "__main__":
    main()
