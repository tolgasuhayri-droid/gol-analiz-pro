import os,json,time
from pathlib import Path
from datetime import datetime,timezone
import requests
LEAGUES={39,140,135,78,61,203,2,3,848,88,94,144}
STATE=Path('live_state.json'); OUT=Path('live.json')

def load():
    return json.loads(STATE.read_text()) if STATE.exists() else {}
def save(path,data):
    tmp=path.with_suffix('.tmp'); tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2)); tmp.replace(path)
def api(endpoint,**params):
    r=requests.get('https://v3.football.api-sports.io/'+endpoint,params=params,headers={'x-apisports-key':os.environ['API_FOOTBALL_KEY']},timeout=25); r.raise_for_status(); d=r.json()
    if d.get('errors'): raise RuntimeError(str(d['errors']))
    return d['response']
def stats(rows):
    if len(rows)!=2:return None
    maps=[{s['type']:s['value'] for s in t['statistics']} for t in rows]
    out={}
    for key,name in [('shots','Total Shots'),('target','Shots on Goal'),('corners','Corner Kicks'),('inside','Shots insidebox'),('xg','expected_goals')]:
        try:out[key]=sum(float(m[name]) for m in maps)
        except (KeyError,TypeError,ValueError):out[key]=None
    return out

def odds(rows):
    for row in rows:
        for market in row.get('odds',[]):
            name=market.get('name','').lower()
            if not ('half' in name and ('over/under' in name or 'over under' in name) and ('first' in name or '1st' in name)):continue
            for v in market.get('values',[]):
                if str(v.get('value','')).lower() in ('over','over 0.5') and str(v.get('handicap','0.5'))=='0.5' and not v.get('suspended') and not v.get('blocked'):
                    try:return float(v['odd'])
                    except (ValueError,TypeError,KeyError):pass
    return None

def assess(base,now,minute):
    if not base or not now or not base.get('odds') or not now.get('odds'):return None
    a,b=base['stats'],now['stats']
    if any(a.get(k) is None or b.get(k) is None for k in ('shots','target','corners','inside')):return None
    if not 25<=minute<=40:return None
    score=20*(a['shots']>=6)+20*(a['target']>=2)+10*(a['corners']>=3)+10*(a['inside']>=3)+15*(b['shots']-a['shots']>=2)+15*(b['target']-a['target']>=1)+10*(now['odds']<=base['odds'])
    return score

def run():
    state=load(); now=datetime.now(timezone.utc).isoformat(); cards=[]
    fixtures=api('fixtures',live='all')
    for f in fixtures:
        if f['league']['id'] not in LEAGUES:continue
        fid=str(f['fixture']['id']); status=f['fixture']['status']; minute=status.get('elapsed') or 0
        rec=state.setdefault(fid,{'home':f['teams']['home']['name'],'away':f['teams']['away']['name'],'league':f['league']['name']})
        half=f.get('score',{}).get('halftime') or {}
        if rec.get('selection') and half.get('home') is not None and half.get('away') is not None:rec['result']='success' if half['home']+half['away']>0 else 'failure'
        if status['short']!='1H' or not 1<=minute<=40 or f['goals']!={'home':0,'away':0}:continue
        s=stats(api('fixtures/statistics',fixture=fid)); o=odds(api('odds/live',fixture=fid))
        if not s:continue
        snap={'minute':minute,'stats':s,'odds':o,'time':now}
        rec.setdefault('history',{})[str(minute)]=snap
        if minute==20:rec['baseline']=snap
        score=assess(rec.get('baseline'),snap,minute)
        if score is not None and score>=80 and not rec.get('selection'):rec['selection']={'minute':minute,'score':score,'odds':o}
        cards.append({'home':rec['home'],'away':rec['away'],'league':rec['league'],'minute':minute,'baseline':rec.get('baseline'),'current':snap,'score':score,'selection':rec.get('selection')})
    # Resolve selections that disappeared from live feed.
    for fid,rec in state.items():
        if rec.get('selection') and not rec.get('result') and not any(str(f['fixture']['id'])==fid for f in fixtures):
            rows=api('fixtures',id=fid)
            if rows:
                h=rows[0].get('score',{}).get('halftime') or {}
                if h.get('home') is not None and h.get('away') is not None:rec['result']='success' if h['home']+h['away']>0 else 'failure'
    save(STATE,state); save(OUT,{'updated_at':now,'matches':cards,'success':sum(r.get('result')=='success' for r in state.values()),'failure':sum(r.get('result')=='failure' for r in state.values())})
if __name__=='__main__':run()
