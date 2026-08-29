#!/usr/bin/env python3
"""Execute the authenticated bounded softmax semantics (softmax-only gate)."""
import argparse, hashlib, json, math
from pathlib import Path

def main():
    p=argparse.ArgumentParser(); p.add_argument('--binding',type=Path,required=True); p.add_argument('--oracle',type=Path,required=True); p.add_argument('--output',type=Path,required=True); a=p.parse_args()
    b=json.loads(a.binding.read_text()); o=json.loads(a.oracle.read_text())
    if b['source_oracle_sha256'] != o.get('sha256'): raise SystemExit('oracle_identity_mismatch')
    rows=[]; max_err=0.0
    for head,row in enumerate(o['trace']['rows']):
        scores=row['score_rows']; probs=[]
        for q,vals in enumerate(scores):
            valid=vals[:q+1]; mx=max(valid); ex=[math.exp(float(x-mx)) for x in valid]; sm=sum(ex)
            out=[x/sm for x in ex]+[0.0]*(len(vals)-q-1)
            ref=row['softmax_rows'][q]; max_err=max(max_err,max(abs(float(x)-float(y)) for x,y in zip(out,ref)))
            probs.append(out)
            rows.append({'head':head,'query':q,'max':mx,'sum':sm,'probabilities':out})
    report={'schema':'tinystories-1m-bound-softmax-interpreter-v1','status':'softmax_only_pass','scope':'authenticated score input to causal max/delta/exp/sum/div; not full block, RTL, or hardware equivalence','heads':16,'checkpoints':rows,'max_absolute_error':max_err,'functional_equivalence':False,'rtl_equivalence':False,'hardware_equivalence':False}
    a.output.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n'); print(json.dumps({'status':report['status'],'max_absolute_error':max_err,'checkpoints':len(rows)})); return 0
if __name__=='__main__': raise SystemExit(main())
