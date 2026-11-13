"""Fetch info about a YouTube URL without downloading."""
import sys
sys.path.insert(0, ".")
import yt_dlp

url = "https://youtu.be/C6w075EfZHk?si=4a30ZxbO2CiS3hsz"
opts = {
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    "nocheckcertificate": True,
}
with yt_dlp.YoutubeDL(opts) as ydl:
    info = ydl.extract_info(url, download=False)

print(f"Title    : {info.get('title')}")
print(f"Artist   : {info.get('uploader') or info.get('channel')}")
print(f"Duration : {info.get('duration')}s ({info.get('duration', 0)//60}m {info.get('duration', 0)%60}s)")
print(f"URL      : {info.get('webpage_url')}")

