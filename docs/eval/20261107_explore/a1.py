import json,collections as C
U=json.load(open('units.json',encoding='utf8'))
def state(u):
    if not u['file_tested']: return 'cold_file'
    if u['func_tested'] is None: return 'module'
    return 'partial_func' if u['func_tested'] else 'cold_func'
def logic(u): return u['branch']+u['raise_']+u['except_']>0
for u in U: u['state']=state(u); u['logic']=logic(u)
print('units',len(U),'lines',sum(u['lines'] for u in U))
print('\n단위별: state x logic (units, gap lines, defect lines) -- SZZ 커밋만 defect 의미')
szz={'24faf5b','3db2f31','568ea41','82e4305','99309f2','9e9c12b','adb2f5b','b67e806','da30a78','f2d690e','f57b432'}
t=C.defaultdict(lambda:[0,0,0,0])
for u in U:
    if u['sha'] in szz:
        k=(u['state'],u['logic']); t[k][0]+=1;t[k][1]+=u['lines'];t[k][2]+=u['defect'];t[k][3]+=u['defect']>0
for k,v in sorted(t.items()): print(k,'units',v[0],'lines',v[1],'defect_lines',v[2],'defect_units',v[3],'rate/unit %.2f rate/line %.2f'%(v[3]/v[0],v[2]/v[1]))
print('\n파일상태')
t=C.defaultdict(lambda:[0,0,0])
for u in U:
    if u['sha'] in szz:
        k=(u['file_status'],u['path'].split('/')[1] if '/' in u['path'] else ''); t[k][0]+=1;t[k][1]+=u['lines'];t[k][2]+=u['defect']
for k,v in sorted(t.items(),key=str): print(k,v)
print('\n커밋 요약 (labeled)')
by=C.defaultdict(list)
for u in U: by[u['sha']].append(u)
rows=[]
for sha,us in by.items():
    u0=us[0]
    if u0['need'] is None: continue
    n=sum(u['lines'] for u in us)
    st=C.Counter()
    for u in us: st[u['state']]+=u['lines']
    lg=sum(u['lines'] for u in us if u['logic'])
    pl=sum(u['lines'] for u in us if u['logic'] and u['state']!='cold_file')
    allnew=all(u['file_status']=='A' for u in us)
    rows.append((u0['need'],u0['reason'],sha,u0['set'],f"{u0['commit_gap']}/{u0['commit_exec']}",dict(st),'logic',lg,'logic_tested_file',pl,'units',len(us),'paths',sorted({u['path'] for u in us})[:3]))
for r in sorted(rows,key=lambda r:(r[0],r[1])): print(r)
