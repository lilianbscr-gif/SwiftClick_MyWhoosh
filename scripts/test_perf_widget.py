"""Teste le fetch intervals.icu et simule l'affichage du widget."""
from intervals_client import IntervalsClient

c = IntervalsClient()
print(f"Enabled: {c.enabled}")

data = c.fetch_all()
print(f"Data brute: {data}")

ctl = data.get("ctl")
atl = data.get("atl")
tsb = data.get("tsb")
ftp = data.get("ftp")

def bar(val, scale=80):
    if val is None:
        return "—"
    filled = min(5, max(0, round(val / (scale / 5))))
    return "▰" * filled + "▱" * (5 - filled)

def tsb_label(t):
    if t is None:  return "—"
    if t > 5:      return f"+{t:.1f}  EN FORME"
    if t > -10:    return f"{t:.1f}  EQUILIBRE"
    if t > -30:    return f"{t:.1f}  FATIGUE"
    return             f"{t:.1f}  SURCHARGE"

print()
print("== PERFORMANCE DU JOUR ==")
print(f"  FORME   (CTL)  {bar(ctl)}  {ctl}")
print(f"  FATIGUE (ATL)  {bar(atl)}  {atl}")
print(f"  BALANCE (TSB)  {tsb_label(tsb)}")
ftp_txt = f"{ftp} W" if ftp else "— W  (calcul en cours)"
print(f"  FTP            {ftp_txt}")
