#!/usr/bin/env python3
import argparse,json
from pathlib import Path
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
 # Simulated serial paths, at 100 MHz. Values are from immutable receipts.
 stages=[('qkv_frontend',191225000),('attention_residual',90905000),('mlp_residual',343825000)]
 total=sum(t for _,t in stages); cycles=round(total/10000); # ps per 100-MHz cycle
 m={'qkv_weights_bytes':3*64*64,'attention_out_weights_bytes':64*64,'mlp_weights_bytes':256*64+64*256,'activation_bytes':(64+16*4+256+64)*4}
 out={'schema':'tinystories-1m-one-block-metrics-v1','status':'measured_serial_slice_summary','clock_hz':100000000,'stages':[{'name':n,'simulated_time_ps':t,'cycles_at_100mhz':round(t/10000)} for n,t in stages],'aggregate':{'simulated_time_ps':total,'cycles_at_100mhz':cycles,'tokens_per_second_if_serial':100000000/cycles},'memory':m,'claims':{'functional_subpaths_verified':True,'complete_block_latency':False,'timing_closed':False,'hardware_throughput':False}}
 a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
if __name__=='__main__':main()
