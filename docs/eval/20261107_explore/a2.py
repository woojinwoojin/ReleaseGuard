import json,collections as C,sys
sys.stdout.reconfigure(encoding='utf-8')
U=json.load(open('units.json',encoding='utf8'))
for u in U:
    u['logic']=u['branch']+u['raise_']+u['except_']>0
    u['exp']=u['path'].startswith(('experiments/','scripts/','notebooks/'))
    u['cold']=not u['file_tested']
by=C.defaultdict(list)
for u in U: by[u['sha']].append(u)
def auc(pos,neg):
    w=sum((p>n)+.5*(p==n) for p in pos for n in neg); return w/(len(pos)*len(neg))
S={
 'gap_lines':lambda us:sum(u['lines'] for u in us),
 'gap_ratio':lambda us:us[0]['commit_gap']/max(1,us[0]['commit_exec']),
 'units':lambda us:len(us),
 'logic_lines':lambda us:sum(u['lines'] for u in us if u['logic']),
 'logic_units':lambda us:sum(u['logic'] for u in us),
 'logic_lines_noexp':lambda us:sum(u['lines'] for u in us if u['logic'] and not u['exp']),
 'logic_units_noexp':lambda us:sum(u['logic'] and not u['exp'] for u in us),
 'units_noexp':lambda us:sum(not u['exp'] for u in us),
 'lines_noexp':lambda us:sum(u['lines'] for u in us if not u['exp']),
}
OVER=['99309f2','c7733b3','ef7ed86','1d72d34','4e3d04a','2e652ab','7df65e6']
ff=[s for s,us in by.items() if us[0]['reason']=='followup_fix']
yes=[s for s,us in by.items() if us[0]['need']=='yes']
print('over',len(OVER),'followup',len(ff),ff,'yes',len(yes))
for k,f in S.items():
    print(f"{k:20s} AUC ff-vs-over {auc([f(by[s]) for s in ff],[f(by[s]) for s in OVER]):.3f}  yes-vs-over {auc([f(by[s]) for s in yes],[f(by[s]) for s in OVER]):.3f}")
print('\n공백 단위 순위 (SZZ 결함이 공백에 있는 커밋)')
order={
 'source_order':lambda u,i:i,
 'size_desc':lambda u,i:-u['lines'],
 'logic_then_size':lambda u,i:(not u['logic'],-u['lines']),
 'logic_cold_size':lambda u,i:(not u['logic'],not u['cold'],-u['lines']),
 'partial_first':lambda u,i:(u['func_tested'] is not True,-u['lines']),
}
ds=[s for s,us in by.items() if any(u['defect'] for u in us)]
print('commits',len(ds),[ (s,len(by[s]),sum(u['defect']>0 for u in by[s])) for s in ds])
for name,key in order.items():
    hit1=hit3=mrr=rec3=0;tot=0;frac=[]
    for s in ds:
        us=by[s]; r=sorted(enumerate(us),key=lambda t:(key(t[1],t[0]),t[0]) )
        ranks=[i+1 for i,(_,u) in enumerate(r) if u['defect']]
        hit1+=ranks[0]==1;hit3+=ranks[0]<=3;mrr+=1/ranks[0]
        rec3+=sum(x<=3 for x in ranks);tot+=len(ranks);frac.append(ranks[0]/len(us))
    print(f"{name:18s} first-hit@1 {hit1}/{len(ds)} @3 {hit3}/{len(ds)} MRR {mrr/len(ds):.2f} defect-units-in-top3 {rec3}/{tot} mean first pos frac {sum(frac)/len(frac):.2f}")
print('\nno-logic 공백 내용 (need=yes 소형)')
for s in ['5b31f70','7f9efeb','4f9c0f0','93abf12']:
    for u in by[s]: print(s,u['path'],u['unit'],u['lines'],'logic',u['logic'],'cold',u['cold'],'func_tested',u['func_tested'])
