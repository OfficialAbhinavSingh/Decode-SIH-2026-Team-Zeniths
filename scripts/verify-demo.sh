#!/usr/bin/env bash
# Pre-demo check. Run this before you present, and again if anything looks odd on stage.
# Read-only: it never writes to the database.
#
#   ./scripts/verify-demo.sh
#
# Every line is PASS or FAIL. A FAIL tells you what to say, or what not to.

API="${API_URL:-https://neerdrishti-api.onrender.com}"
WEB="${WEB_URL:-https://neerdrishti-web.onrender.com}"
TALLY=$(mktemp); : > "$TALLY"
pass=0; fail=0
ok()   { printf '  \033[32mPASS\033[0m  %s\n' "$1"; echo P >> "$TALLY"; }
bad()  { printf '  \033[31mFAIL\033[0m  %s\n' "$1"; echo F >> "$TALLY"; }
note() { printf '        %s\n' "$1"; }

echo "NeerDrishti pre-demo check   $(date -u +%FT%TZ)"
echo "API $API"
echo

echo "1. Services reachable"
t=$(curl -s -o /dev/null -w '%{time_total}' --max-time 30 "$API/health" 2>/dev/null)
if [ "$(curl -s --max-time 30 "$API/health" | grep -c '"status":"ok"')" = "1" ]; then
  ok "API healthy (${t}s)"
  awk -v t="$t" 'BEGIN{ if (t+0 > 3) exit 0; exit 1 }' && note "slow -- it was asleep. Hit it again before you present."
else bad "API not healthy -- open $API/health"; fi
[ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 "$WEB")" = "200" ] \
  && ok "dashboard serving" || bad "dashboard not serving -- $WEB"
echo

echo "2. Data the demo script depends on"
curl -s --max-time 30 "$API/api/scores" > /tmp/_nd_scores.json 2>/dev/null
python3 - <<PY
import json,sys
try: rows=json.load(open('/tmp/_nd_scores.json'))
except Exception: print("  FAIL  could not read /api/scores"); sys.exit(0)
z={r['zone_id']:r for r in rows}
T=open("$TALLY","a")
def chk(cond,msg):
    print(("  \033[32mPASS\033[0m  " if cond else "  \033[31mFAIL\033[0m  ")+msg)
    T.write("P\n" if cond else "F\n"); T.flush()
chk(len(rows)==30, f"30 zones scored (got {len(rows)})")
r=z.get('Z-005',{}); chk(r.get('rank')==3 and r.get('signals_used')==3,
    f"Z-005 is rank #3 on 3/3 signals (got #{r.get('rank')}, {r.get('signals_used')}/3)")
r=z.get('Z-023',{}); chk(r.get('signals_used')==1 and r.get('confidence')=='low',
    f"Z-023 reads 1/3 signals, low confidence (got {r.get('signals_used')}/3, {r.get('confidence')})")
r=z.get('Z-028',{}); chk(r.get('confidence')=='high' and r.get('rank',0)>20,
    f"Z-028 is high confidence at a low rank (got {r.get('confidence')}, #{r.get('rank')})")
r=z.get('Z-025',{}); chk(r.get('satellite_score')==0,
    f"Z-025 still shows satellite 0 (got {r.get('satellite_score')})")
r=z.get('Z-022',{}); chk(r.get('rank',0)>10,
    f"Z-022 (the bot-test zone) stays out of the top 10 (got #{r.get('rank')})")
one=[r for r in rows if r['signals_used']==1 and r['fusion_score']>=95]
chk(not one, "no zone scores 95+ on a single signal"+(f" (offenders: {[r['zone_id'] for r in one]})" if one else ""))
PY
echo

echo "3. Nothing fabricated"
python3 - <<PY
import json,urllib.request
def get(p):
    with urllib.request.urlopen("$API"+p, timeout=30) as r: return json.load(r)
T=open("$TALLY","a")
def chk(c,m):
    print(("  \033[32mPASS\033[0m  " if c else "  \033[31mFAIL\033[0m  ")+m)
    T.write("P\n" if c else "F\n"); T.flush()
try:
    sig=get("/api/zones/Z-005/signals")
    src={s.get('source') for s in sig.get('satellite',[])}
    chk('seed' not in src, f"satellite rows are real GEE exports, not seeded (source={src or 'none'})")
    chk(all(s.get('is_synthetic') for s in sig.get('billing',[])),
        "billing rows are flagged is_synthetic (say 'modelled' on stage, not 'real')")
    reps=get("/api/reports")
    counted=[r for r in reps if r['status']=='new']
    words=('/help','hello?','hi','test','ok','thanks','pothole','pothole damage','/start')
    junk=[r for r in counted if (r.get('description') or '').strip().lower() in words]
    scoring=[r for r in junk if r.get('zone_id')]
    orphan=[r for r in junk if not r.get('zone_id')]
    chk(not scoring, f"no greeting or off-topic message is moving a zone score ({len(scoring)} found)")
    if orphan:
        print(f"        note: {len(orphan)} off-topic rows sit at status 'new' with no zone "
              f"(ids {[r['id'] for r in orphan]}). They score nothing, but they show in the feed.")
    chk(len(reps)>0, f"{len(reps)} reports total, {len(counted)} counted toward scores")
except Exception as e:
    print("  \033[31mFAIL\033[0m  could not check signals/reports:",e)
PY
echo

echo "4. Offline safety net"
[ -f frontend/public/basemap.jpg ] && ok "bundled basemap present ($(du -h frontend/public/basemap.jpg | cut -f1))" \
  || bad "frontend/public/basemap.jpg missing -- the map dies without wifi"
docker image inspect decode-sih-2026-team-zeniths-api:latest >/dev/null 2>&1 \
  && ok "API docker image cached (docker compose up works with no internet)" \
  || bad "API image not built -- run 'docker compose build api' while you still have wifi"
ss -ltn 2>/dev/null | grep -q ':8000 ' \
  && { bad "port 8000 is already taken on this machine"; note "the API cannot bind. Stop the other process before the demo."; } \
  || ok "port 8000 is free"
echo

echo "-----------------------------------------------"
pass=$(grep -c P "$TALLY" 2>/dev/null || echo 0)
fail=$(grep -c F "$TALLY" 2>/dev/null || echo 0)
rm -f "$TALLY"
printf 'PASS %d   FAIL %d\n' "$pass" "$fail"
[ "$fail" -gt 0 ] && echo "Fix the FAIL lines before you present." || echo "Everything checked out."
