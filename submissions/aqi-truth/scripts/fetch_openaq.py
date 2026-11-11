"""Download hourly OpenAQ archive files (public S3 bucket, no key) for Delhi stations.
Usage: python fetch_openaq.py OUTDIR YEAR MONTH[,MONTH...] [location_id ...]"""
import gzip, io, os, re, sys, time, urllib.request
BASE = "https://openaq-data-archive.s3.amazonaws.com"
DELHI = {  # OpenAQ location ids for Delhi CAAQMS stations with 2025 data
 235:"Anand Vihar",17:"R K Puram",8915:"Wazirpur",8917:"Ashok Vihar",10484:"Sri Aurobindo Marg",10485:"Narela",
 10486:"Mundka",10488:"Najafgarh",8235:"Jahangirpuri",8239:"Okhla Phase-2",5570:"Aya Nagar",8472:"Bawana",
 8365:"Nehru Nagar",8475:"Sonia Vihar",5610:"North Campus DU",5627:"CRRI Mathura Road",5634:"Lodhi Road IMD",
 5650:"IGI Airport T3",6359:"IHBAS Dilshad Garden",6356:"Pusa DPCC",6932:"Alipur",6957:"JLN Stadium",
 6934:"Dr Karni Singh Shooting Range",6931:"Dwarka Sec 8",6929:"Major Dhyan Chand Stadium",6938:"Vivek Vihar",
 6960:"Patparganj",10831:"Rohini",50:"Punjabi Bagh",5541:"Burari Crossing",5613:"ITO",11603:"Chandni Chowk",
 11607:"Lodhi Road IITM",5404:"Pusa IMD",8118:"US Embassy New Delhi"}
def get(url, tries=4):
    for i in range(tries):
        try: return urllib.request.urlopen(url, timeout=60).read()
        except Exception as e:
            if i == tries-1: raise
            time.sleep(2**i)
def keys(prefix):
    out, token = [], None
    while True:
        u = f"{BASE}/?list-type=2&prefix={prefix}" + (f"&continuation-token={urllib.parse.quote(token)}" if token else "")
        x = get(u).decode()
        out += re.findall(r"<Key>([^<]+)</Key>", x)
        m = re.search(r"<NextContinuationToken>([^<]+)</NextContinuationToken>", x)
        if not m: return out
        token = m.group(1)
import urllib.parse
out, year, months = sys.argv[1], sys.argv[2], sys.argv[3].split(",")
ids = [int(a) for a in sys.argv[4:]] or list(DELHI)
os.makedirs(out, exist_ok=True)
for lid in ids:
    for mo in months:
        dest = f"{out}/loc{lid}-{year}-{mo}.csv"
        if os.path.exists(dest): continue
        ks = keys(f"records/csv.gz/locationid={lid}/year={year}/month={mo}/")
        buf = []
        for k in ks:
            t = gzip.decompress(get(f"{BASE}/{k}")).decode("utf-8").splitlines()
            buf += t[1:]
        open(dest+".tmp","w").write("\n".join(buf)); os.rename(dest+".tmp", dest)
        print(lid, DELHI.get(lid), year, mo, len(ks), "files", len(buf), "rows", flush=True)
