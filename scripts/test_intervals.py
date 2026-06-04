"""Test connexion API intervals.icu."""
import urllib.request, base64, json, ssl, datetime

ctx     = ssl.create_default_context()
ATHLETE = "i603948"
API_KEY = "5yy89i76n2pb2yoxsqc3bmaw3"
creds   = base64.b64encode(f"API_KEY:{API_KEY}".encode()).decode()
UA      = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
           "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

def get(path):
    req = urllib.request.Request(
        f"https://intervals.icu/api/v1{path}",
        headers={"Authorization": f"Basic {creds}",
                 "Accept": "application/json",
                 "User-Agent": UA}
    )
    with urllib.request.urlopen(req, timeout=12, context=ctx) as r:
        return json.loads(r.read())

# Profil
p = get(f"/athlete/{ATHLETE}")
print(f"Profil : name={p.get('name')}  ftp={p.get('ftp')}  VO2max={p.get('vo2max')}")
print(f"  weight={p.get('weight')}kg  sex={p.get('sex')}")

# Wellness CTL/ATL/TSB (30 derniers jours)
today    = datetime.date.today().isoformat()
month_ago = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
ws = get(f"/athlete/{ATHLETE}/wellness?oldest={month_ago}&newest={today}")
print(f"\nWellness : {len(ws)} entrees")
if ws:
    last = ws[-1]
    print(f"  Dernier ({last.get('id')}) : CTL={last.get('ctl')}  ATL={last.get('atl')}  TSB={last.get('tsb')}")
    print(f"  Cles dispo : {[k for k in last if last[k] is not None]}")

# Activites
acts = get(f"/athlete/{ATHLETE}/activities?oldest={month_ago}&newest={today}")
print(f"\nActivites : {len(acts)} trouvees")
for a in acts[:5]:
    mins = (a.get("moving_time") or 0) // 60
    print(f"  {a.get('start_date_local','?')[:10]}  {a.get('type','?'):12}  {a.get('name','?')[:30]}  {mins}min")
    print(f"    TSS={a.get('tss')}  IF={a.get('intensity_factor')}  watts={a.get('average_watts')}")
