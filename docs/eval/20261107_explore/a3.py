import json,collections as C,sys,random
sys.stdout.reconfigure(encoding='utf-8')
U=json.load(open('units.json',encoding='utf8'))
by=C.defaultdict(list)
for u in U: by[u['sha']].append(u)
ds=[s for s,us in by.items() if any(u['defect'] for u in us)]
# top3 by size: 공백 줄 비중 vs 결함 줄 비중
gl=gt=dl=dt=0
for s in ds:
    r=sorted(by[s],key=lambda u:-u['lines']); t=r[:3]
    gl+=sum(u['lines'] for u in t);gt+=sum(u['lines'] for u in r);dl+=sum(u['defect'] for u in t);dt+=sum(u['defect'] for u in r)
print('top3 share of gap lines %.2f, of defect lines %.2f (%d/%d)'%(gl/gt,dl/dt,dl,dt))
# 줄 수 비례 무작위 기준: 결함 단위가 줄 수에 비례해 뽑힌다면 first-hit@1 기대값
exp=0
for s in ds:
    us=by[s];tot=sum(u['lines'] for u in us);top=max(u['lines'] for u in us);exp+=top/tot
print('size-proportional chance that top unit holds a random gap line: mean %.2f'%(exp/len(ds)))
# 줄당 결함 밀도: 크기 구간별
b=C.defaultdict(lambda:[0,0,0])
for s in ds:
    for u in by[s]:
        k='1-2' if u['lines']<=2 else '3-9' if u['lines']<=9 else '10-29' if u['lines']<=29 else '30+'
        b[k][0]+=1;b[k][1]+=u['lines'];b[k][2]+=u['defect']
for k,v in b.items(): print(k,v,'density %.3f'%(v[2]/v[1]))
s=json.load(open('C:/Project_Folder/release-guard/out/eval/v31_branch/20261104_szz.json',encoding='utf8'))
for r in s['rows']:
    if r['sha']=='99309f2':
        for l in r['lines']:
            if l['status']=='gap': print(l['fix'][:7],l['path'],l['line'],l['text'][:90])
