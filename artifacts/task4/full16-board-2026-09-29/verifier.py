import hashlib,json,pathlib,re,sys
hardware,oracle_path,candidate,authority,out=map(pathlib.Path,sys.argv[1:])
receipt=json.loads((hardware/'receipt.json').read_text())
oracle=json.loads(oracle_path.read_text())
semantic=json.loads((authority/'receipt.json').read_text())
conversion=json.loads((candidate/'receipt.json').read_text())
canonical=json.dumps({k:v for k,v in oracle.items() if k!='artifact_sha256'},sort_keys=True,separators=(',',':'),allow_nan=False).encode()
assert hashlib.sha256(canonical).hexdigest()==oracle['artifact_sha256']==receipt['oracle_sha256']==semantic['oracle_sha256']
expected=[s['selected_token']['value'] for s in oracle['steps']]
assert semantic['status']=='passed' and expected==semantic['tokens'][0] and len(expected)==16
prompt=oracle['token_contract']['initial_context']
assert prompt==[7454,2402,257,640]
bitsha=hashlib.sha256((candidate/'model.bit').read_bytes()).hexdigest()
assert bitsha==receipt['candidate_sha256']==conversion['bitstream_sha256']
assert conversion['bram_modes']['decoded_physical_bits_verified']
assert conversion['bram_modes']['bram36_instances']==813
assert conversion['bram_modes']['projection_mode_features']==29
assert receipt['status']=='passed' and len(receipt['runs'])==3
assert not receipt.get('candidate_error') and not receipt.get('restoration_error')
assert receipt['claims']==dict(bpi_changed=False,full_timing_qualification=False)
latencies=[]
for result in receipt['runs']:
    assert result['status']=='passed' and result['inference_started']
    assert result['tokens']==expected and 0<result['elapsed_seconds']<=300
    transactions=result['transactions']
    commands=[int(t['command'],16) for t in transactions]
    writes=[0x1000000000000000|(i<<16)|v for i,v in enumerate(prompt)]
    reads=[0x6000000000000000|(i<<16) for i in range(4)]
    token_reads=[0x4000000000000000|i for i in range(16)]
    assert [c for c in commands if c>>60==1]==writes
    assert [c for c in commands if c>>60==6]==reads
    assert [c for c in commands if c>>60==4]==token_reads
    assert commands.count(0x2000000000000000)==1 and commands.count(0x5000000000000000)==1
    allowed=set(writes+reads+token_reads+[0x2000000000000000,0x3000000000000000,0x5000000000000000])
    assert all(c in allowed for c in commands)
    start=commands.index(0x2000000000000000)
    assert all(commands.index(c)<start for c in writes+reads)
    captured_tokens=[]
    for i,command in enumerate(commands):
        if command in writes+reads+token_reads:
            assert i+1<len(commands) and commands[i+1]==0x3000000000000000
            actual=int(transactions[i+1]['captured'],16)
            if command in token_reads:
                assert i>start
                captured_tokens.append(actual)
            else:
                index=writes.index(command) if command in writes else reads.index(command)
                assert actual==prompt[index]
    assert captured_tokens==expected
    assert result['last_status']==f'{0x2c00000000000000|prompt[0]:016x}'
    latencies.append(result['elapsed_seconds'])
restored=receipt['baseline_restoration']
assert restored['status']=='passed' and restored['token']==11
events=receipt['programming']
assert [e['label'] for e in events]==['run0','run1','run2','restored-first-token']
for event in events:
    assert event['returncode']==0 and 0<event['elapsed_seconds']<=360
    command=event['command']
    assert command[1:8]==['-c','digilent_hs3','--ftdi-serial','210299BF3824','--freq','1000000','-m'] and len(command)==9
    if event['label'].startswith('run'):
        assert command[8]==str(candidate/'model.bit') and event['image_sha256']==bitsha
    else:
        assert event['image_sha256']=='2e28abb6638b407fd55b681018275c712afe47fde2de24ba8d1ebe584208b91a'
    log=(hardware/(event['label']+'-program.log')).read_text()
    assert 'write to ram' in log and re.search(r'isc_done\s+1\s+isc_ena\s+0\s+init\s+1\s+done\s+1',log)
assert (hardware/'executed-runner.py').is_file()
summary=dict(status='passed',tokens=expected,elapsed_seconds=latencies,
    independently_programmed_SRAM_runs=3,baseline_restored=True,
    bitstream_sha256=bitsha,START_count_per_run=1,host_prompt_writes_per_run=4,
    raw_indexed_TDO_tokens_verified=True,full_timing_qualification=False,
    scope='BRAM/LUTRAM, 30 MHz, JTAG; independent SRAM reconfiguration, not chassis power cycles; PCIe/DDR3 not covered')
(out/'verification.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
