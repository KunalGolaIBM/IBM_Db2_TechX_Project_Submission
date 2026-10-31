import re, os, hashlib
from urllib.parse import urlparse
from PIL import Image
from PIL.ExifTags import TAGS

URL_RE = re.compile(r'https?://[^\s,]+', re.I)
RISKY_EXT = {'exe','apk','scr','bat','vbs','js','jar'}
MAGIC = {b'%PDF':'pdf', b'\x89PNG':'png', b'\xff\xd8\xff':'jpg', b'MZ':'exe', b'PK\x03\x04':'zip'}

def _out(name, score, flags):
    return {'inspector': name, 'score': min(score, 100), 'flags': flags}

# 1. MESSAGE inspector
def inspect_message(text):
    t, f, s = text.lower(), [], 0
    checks = [
        ('Urgency / threat language', ['urgent','blocked','suspend','final warning','immediately','expires','disconnected','seats left','legal action'], 25),
        ('Asks for sensitive data (OTP/CVV/PIN)', ['otp','cvv','pin ','password','net banking'], 35),
        ('Asks for money / fee', ['processing fee','registration fee','pay rs','pay now','lucky draw','you won'], 30),
        ('Impersonates a known brand', ['sbi','jio','amazon','india post','hdfc','icici','paytm','rbi'], 15),
    ]
    for label, words, pts in checks:
        if any(w in t for w in words): f.append(label); s += pts
    return _out('Message Inspector', s, f)

# 2. LINK inspector
def inspect_links(text):
    f, s = [], 0
    for u in URL_RE.findall(text):
        host = urlparse(u).hostname or ''
        if u.lower().startswith('http://'): f.append(f'{host}: no HTTPS'); s += 15
        if host.split('.')[0] in ('bit','tinyurl','t','goo') or host.count('.') >= 3:
            f.append(f'{host}: shortener / stacked subdomains'); s += 25
        if host.count('-') >= 1 and any(b in host for b in ['sbi','jio','amazon','post','hdfc','bijli','kyc']):
            f.append(f'{host}: lookalike brand domain'); s += 35
        if host.endswith(('.xyz','.top','.click','.tk','.example')):
            f.append(f'{host}: suspicious domain ending'); s += 20
    return _out('Link Inspector', s, f)

# 3. FILE inspector (type, extension, hash)
def inspect_file(path):
    data = open(path,'rb').read()
    name = os.path.basename(path).lower()
    ext = name.rsplit('.',1)[-1]
    real = next((v for k,v in MAGIC.items() if data.startswith(k)), 'unknown')
    f, s = [], 0
    if name.count('.') > 1: f.append('Double extension'); s += 40
    if ext in RISKY_EXT or real == 'exe': f.append('Executable / installer file'); s += 45
    if real != 'unknown' and ext not in real and not (real=='zip' and ext in ('docx','xlsx','pptx','apk','jar')):
        f.append(f'Extension .{ext} but real type is {real}'); s += 35
    r = _out('File Inspector', s, f)
    r.update(real_type=real, size=len(data), sha256=hashlib.sha256(data).hexdigest())
    return r

# 4. MEDIA / CONTENT inspector (metadata, scripts, macros)
def inspect_media(path):
    data = open(path,'rb').read()
    f, s, meta = [], 0, {}
    if b'/JavaScript' in data or b'/OpenAction' in data: f.append('PDF contains script'); s += 45
    if b'vbaProject' in data: f.append('Office macro found'); s += 45
    try:
        exif = Image.open(path).getexif()
        meta = {str(TAGS.get(k,k)): str(v) for k,v in exif.items()}
        if not meta: f.append('No metadata (stripped or edited)'); s += 20
        sw = meta.get('Software','').lower()
        if any(x in sw for x in ('photoshop','gimp','canva','editor')):
            f.append(f'Edited with {meta["Software"]}'); s += 30
    except Exception:
        pass
    r = _out('Media Inspector', s, f); r['metadata'] = meta
    return r

# COMBINED
def analyze(text=None, path=None):
    results = []
    if text:
        results += [inspect_message(text), inspect_links(text)]
    if path:
        results += [inspect_file(path), inspect_media(path)]
    scores = sorted((r['score'] for r in results), reverse=True)
    total = min(100, int(scores[0] + 0.3*sum(scores[1:]))) if scores else 0
    risk = 'HIGH' if total >= 60 else 'MEDIUM' if total >= 30 else 'LOW'
    return {'overall_score': total, 'risk': risk, 'inspectors': results}
CHECKS = {
    'Message Inspector': [('Urgency / threat language', 'urgency'),
                          ('Asks for OTP / CVV / password', 'sensitive data'),
                          ('Asks for money / fee', 'money'),
                          ('Impersonates a known brand', 'impersonates')],
    'Link Inspector':    [('Uses HTTPS', 'no https'),
                          ('Not a shortener / stacked subdomain', 'shortener'),
                          ('Not a lookalike brand domain', 'lookalike'),
                          ('Safe domain ending', 'suspicious domain')],
    'File Inspector':    [('No double extension', 'double extension'),
                          ('Not an executable / installer', 'executable'),
                          ('Extension matches real type', 'real type')],
    'Media Inspector':   [('No embedded script', 'script'),
                          ('No Office macro', 'macro'),
                          ('Metadata present', 'no metadata'),
                          ('Not edited with editing software', 'edited with')],
}

def analyze_detailed(text=None, path=None):
    base = analyze(text=text, path=path)
    total = sum(i['score'] for i in base['inspectors']) or 1
    failed_all = checks_all = 0
    for i in base['inspectors']:
        flags = [f.lower() for f in i['flags']]
        i['checks'] = [
            {'check': label,
             'status': 'FAILED' if any(k in f for f in flags) else 'PASSED'}
            for label, k in CHECKS.get(i['inspector'], [])
        ]
        nf = sum(c['status'] == 'FAILED' for c in i['checks'])
        i['checks_failed'] = nf
        i['checks_total'] = len(i['checks'])
        i['failed_ratio_pct'] = round(100 * nf / max(len(i['checks']), 1), 1)
        i['contribution_to_risk_pct'] = round(100 * i['score'] / total, 1)
        i['verdict'] = 'HIGH' if i['score'] >= 60 else 'MEDIUM' if i['score'] >= 30 else 'LOW'
        failed_all += nf
        checks_all += len(i['checks'])
    base['summary'] = (f"{failed_all} of {checks_all} checks failed "
                       f"({round(100 * failed_all / max(checks_all, 1), 1)}%) "
                       f"across {len(base['inspectors'])} inspectors. "
                       f"Overall risk: {base['risk']} ({base['overall_score']}/100).")
    return base