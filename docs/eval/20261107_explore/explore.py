import ast, json, sys, re
from dataclasses import asdict
from pathlib import Path
RG=Path(r'C:/Project_Folder/release-guard'); sys.path.insert(0,str(RG))
from releaseguard.classify import classify, load_rules
from releaseguard.git_ops import collect, read_file
from releaseguard.runner import run_tests, find_python
from releaseguard.gaps import compute
from releaseguard.evaluate import load_yaml
import inspect
SETS={'predict':'cases.yaml','week1':'cases_week1.yaml','week2':'cases_week2.yaml','week3':'cases_week3.yaml'}
szz=json.load(open(RG/'out/eval/v31_branch/20261104_szz.json',encoding='utf8'))
defect={}
for r in szz['rows']:
    for l in r['lines']:
        defect.setdefault(r['sha'],set()).add((l['path'],l['line']))
def scopes(tree):
    out=[]
    def walk(n,q):
        for c in ast.iter_child_nodes(n):
            if isinstance(c,(ast.FunctionDef,ast.AsyncFunctionDef)):
                nq=q+[c.name]; out.append(('.'.join(nq),c)); walk(c,nq)
            elif isinstance(c,ast.ClassDef): walk(c,q+[c.name])
            else: walk(c,q)
    walk(tree,[]); return out
def struct(nodes):
    f=dict(branch=0,raise_=0,except_=0,ret=0,compute=0,calls=0,io=0)
    for top in nodes:
        for n in ast.walk(top):
            if isinstance(n,(ast.If,ast.While,ast.For,ast.IfExp,ast.Match) if hasattr(ast,'Match') else (ast.If,)): f['branch']+=1
            if isinstance(n,ast.Raise): f['raise_']+=1
            if isinstance(n,ast.ExceptHandler): f['except_']+=1
            if isinstance(n,ast.Return): f['ret']+=1
            if isinstance(n,(ast.BinOp,ast.Compare,ast.BoolOp)): f['compute']+=1
            if isinstance(n,ast.Call):
                f['calls']+=1
                t=ast.unparse(n.func)
                if t=='print' or t.startswith(('st.','logger','logging','console')): f['io']+=1
    return f
rows=[]
rules=load_rules(RG/'configs/rules.yaml') if 'load_rules' in globals() else None
for name,y in SETS.items():
    repo,raw,python=load_yaml(RG/'eval'/y)
    ev=json.load(open(RG/f'out/eval/v31_branch/{name}/20261104_eval.json',encoding='utf8'))
    for r in ev['rows']:
        if 'G01' not in r['rules']: continue
        sha=r['sha']; ch=collect(repo,f'{sha}~1',sha)
        files=[]
        for f in ch.files:
            c,_=classify(f.path,rules); files.append({**asdict(f),'category':c})
        py=find_python(ch.repo,python)
        run=run_tests(ch.repo,ch.head_sha,py)
        fls=compute(files,ch.added_lines,run.coverage)
        status={f['path']:f['status'] for f in files}
        for fl in fls:
            if not fl.gap_lines: continue
            cov=run.coverage.get(fl.path)
            tested=set(cov.tests) if cov else set()
            src=read_file(ch.repo,ch.head_sha,fl.path)
            try: tree=ast.parse(src)
            except SyntaxError: print('syntax',fl.path); continue
            sc=scopes(tree)
            gapl=[n for n,s in fl.line_status.items() if s=='gap']
            units={}
            for n in gapl:
                best=None
                for q,node in sc:
                    if node.lineno<=n<=node.end_lineno and (best is None or node.lineno>=best[1].lineno): best=(q,node)
                units.setdefault(best[0] if best else '<module>',[]).append(n)
            for q,ls in units.items():
                node=next((nd for qq,nd in sc if qq==q),None)
                span=set(range(node.lineno,node.end_lineno+1)) if node else set()
                stm=[]
                for st in ast.walk(tree):
                    if isinstance(st,ast.stmt) and st.lineno in ls and not isinstance(st,(ast.FunctionDef,ast.ClassDef,ast.AsyncFunctionDef)): stm.append(st)
                # 얕게: 줄 자신만의 구조
                shallow=[]
                for st in stm:
                    if isinstance(st,(ast.If,ast.While,ast.For)): shallow.append(st.test if hasattr(st,'test') else st.iter); shallow.append(ast.Pass()); 
                    else: shallow.append(st)
                s=struct(shallow); s['branch']+=sum(isinstance(st,(ast.If,ast.While,ast.For)) for st in stm); s['except_']+=sum(1 for st in ast.walk(tree) if isinstance(st,ast.ExceptHandler) and st.lineno in ls)
                d=defect.get(sha,set())
                rows.append(dict(set=name,sha=sha,need=r['need'],reason=r['need_reason'],fix=r['followup_fix'],rules=r['rules'],path=fl.path,unit=q,lines=len(ls),
                  commit_gap=r['gap_lines'],commit_exec=r['executable_lines'],file_status=status.get(fl.path),measured=fl.measured,
                  file_tested=bool(tested),func_tested=bool(span&tested) if node else None,
                  file_covered_changed=fl.covered,defect=sum((fl.path,n) in d for n in ls),**s))
        print(name,sha,run.status,flush=True)
json.dump(rows,open('units.json','w',encoding='utf8'),ensure_ascii=False,indent=0)
print(len(rows))
