# Lowered softmax trace input binding

The textual flat-SCF artifact is not executable: `%alloc_37` is populated by
earlier lowered operators, so a trace runner cannot derive score values from
the softmax loops alone. The required adapter must provide an authenticated
binding with:

```json
{
  "oracle_sha256": "<oracle self hash>",
  "prompt_tokens": [7454, 2402, 257, 640],
  "block_index": 0,
  "score_tensor": {
    "shape": [16, 4, 4],
    "layout": "head,query,key",
    "values": "<canonical float32 payload or hash plus file>"
  }
}
```

The runner must bind this tensor to the pre-mask score producer, execute the
bounded row-max/delta/exp/sum/div loops, and emit ordered checkpoints for all
16 heads. It must reject missing values, shape/layout mismatches, and any
binding not covered by the oracle/package hashes. The current oracle contains
the reference score rows but no lowered-runtime binding; therefore the gate
remains fail-closed and no numerical equivalence is claimed.
