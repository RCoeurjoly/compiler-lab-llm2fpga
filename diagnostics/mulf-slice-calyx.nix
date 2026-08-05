{ circt
, circtLibc
, baseline
, parallel
, affineParallel
, affine
, affineFull
, affineComplete
}:

circt.stdenv.mkDerivation {
  name = "tinystories-w8a8-mulf-slice-calyx";
  nativeBuildInputs = [ circt ];
  buildInputs = [ circtLibc ];
  dontUnpack = true;
  installPhase = ''
    mkdir -p "$out"
    set +e
    ${circt}/bin/circt-opt "${baseline}" \
      --lower-scf-to-calyx="top-level-function=bb0_1652_slice" \
      -o "$out/baseline.calyx.mlir" \
      >"$out/baseline.stdout" 2>"$out/baseline.stderr"
    baseline_status=$?
    ${circt}/bin/circt-opt "${parallel}" \
      --mlir-disable-threading \
      --affine-parallel-unroll \
      --lower-scf-to-calyx="top-level-function=bb0_1652_parallel_slice" \
      -o "$out/parallel.calyx.mlir" \
      >"$out/parallel.stdout" 2>"$out/parallel.stderr"
    parallel_status=$?
    ${circt}/bin/circt-opt "${affineParallel}" \
      --mlir-disable-threading \
      --affine-parallel-unroll \
      --calyx-affine-to-scf \
      --lower-scf-to-calyx="top-level-function=bb0_1652_parallel_slice" \
      -o "$out/affine-parallel.calyx.mlir" \
      >"$out/affine-parallel.stdout" 2>"$out/affine-parallel.stderr"
    affine_parallel_status=$?
    ${circt}/bin/circt-opt "${affineParallel}" \
      --mlir-disable-threading \
      --memory-banking="factors=2" \
      --affine-parallel-unroll \
      --calyx-affine-to-scf \
      --lower-scf-to-calyx="top-level-function=bb0_1652_parallel_slice" \
      -o "$out/banked-parallel.calyx.mlir" \
      >"$out/banked-parallel.stdout" 2>"$out/banked-parallel.stderr"
    banked_parallel_status=$?
    ${circt}/bin/circt-opt "${affineParallel}" \
      --affine-ploop-unparallelize \
      --calyx-affine-to-scf \
      --lower-scf-to-calyx="top-level-function=bb0_1652_parallel_slice" \
      -o "$out/unparallelized.calyx.mlir" \
      >"$out/unparallelized.stdout" 2>"$out/unparallelized.stderr"
    unparallelized_status=$?
    ${circt}/bin/circt-opt "${affine}" \
      --calyx-affine-to-scf \
      --lower-scf-to-calyx="top-level-function=bb0_1652_affine_slice" \
      -o "$out/affine.calyx.mlir" \
      >"$out/affine.stdout" 2>"$out/affine.stderr"
    affine_status=$?
    ${circt}/bin/circt-opt "${affineFull}" \
      --calyx-affine-to-scf \
      --lower-scf-to-calyx="top-level-function=bb0_1652_affine_slice" \
      -o "$out/affine-full.calyx.mlir" \
      >"$out/affine-full.stdout" 2>"$out/affine-full.stderr"
    affine_full_status=$?
    ${circt}/bin/circt-opt "${affineComplete}" \
      --calyx-affine-to-scf \
      --lower-scf-to-calyx="top-level-function=bb0_1652_affine_slice" \
      -o "$out/affine-complete.calyx.mlir" \
      >"$out/affine-complete.stdout" 2>"$out/affine-complete.stderr"
    affine_complete_status=$?
    if test "$baseline_status" -eq 0; then
      ${circt}/bin/circt-opt "$out/baseline.calyx.mlir" \
        --calyx-gicm \
        -o "$out/gicm.calyx.mlir" \
        >"$out/gicm.stdout" 2>"$out/gicm.stderr"
      gicm_status=$?
      ${circt}/bin/circt-opt "$out/baseline.calyx.mlir" \
        --calyx-remove-comb-groups \
        -o "$out/no-comb-groups.calyx.mlir" \
        >"$out/no-comb-groups.stdout" 2>"$out/no-comb-groups.stderr"
      no_comb_status=$?
      ${circt}/bin/circt-opt "$out/baseline.calyx.mlir" \
        --calyx-remove-groups \
        -o "$out/removed-groups.calyx.mlir" \
        >"$out/removed-groups.stdout" 2>"$out/removed-groups.stderr"
      removed_groups_status=$?
      ${circt}/bin/circt-opt "$out/baseline.calyx.mlir" \
        --calyx-go-insertion --calyx-gicm --calyx-compile-control \
        -o "$out/component-optimized.calyx.mlir" \
        >"$out/component-optimized.stdout" 2>"$out/component-optimized.stderr"
      component_status=$?
    else
      gicm_status=1
      no_comb_status=1
      banked_parallel_status=1
      unparallelized_status=1
      affine_full_status=1
      affine_complete_status=1
      removed_groups_status=1
      component_status=1
      : >"$out/component-optimized.calyx.mlir"
      : >"$out/component-optimized.stderr"
      : >"$out/gicm.calyx.mlir"
      : >"$out/gicm.stderr"
      : >"$out/no-comb-groups.calyx.mlir"
      : >"$out/no-comb-groups.stderr"
      : >"$out/removed-groups.calyx.mlir"
      : >"$out/removed-groups.stderr"
    fi
    set -e
    {
      echo '{'
      echo '  "baseline": {'
      echo "    \"exit_code\": $baseline_status,"
      echo "    \"generated\": $(test -s "$out/baseline.calyx.mlir" && echo true || echo false),"
      echo "    \"bytes\": $(wc -c < "$out/baseline.calyx.mlir" 2>/dev/null || echo 0),"
      echo "    \"calyx_groups\": $(grep -o 'calyx.group' "$out/baseline.calyx.mlir" 2>/dev/null | wc -l),"
      echo "    \"error\": \"$(tr '\n' ' ' < "$out/baseline.stderr" | sed 's/\\\"/\\\\\\\"/g')\""
      echo '  },'
      echo '  "parallel": {'
      echo "    \"exit_code\": $parallel_status,"
      echo "    \"generated\": $(test -s "$out/parallel.calyx.mlir" && echo true || echo false),"
      echo "    \"bytes\": $(wc -c < "$out/parallel.calyx.mlir" 2>/dev/null || echo 0),"
      echo "    \"calyx_groups\": $(grep -o 'calyx.group' "$out/parallel.calyx.mlir" 2>/dev/null | wc -l),"
      echo "    \"error\": \"$(tr '\n' ' ' < "$out/parallel.stderr" | sed 's/\\\"/\\\\\\\"/g')\""
      echo '  }'
      echo '  , "removed_groups": {'
      echo "    \"exit_code\": $removed_groups_status,"
      echo "    \"generated\": $(test -s "$out/removed-groups.calyx.mlir" && echo true || echo false),"
      echo "    \"bytes\": $(wc -c < "$out/removed-groups.calyx.mlir" 2>/dev/null || echo 0),"
      echo "    \"calyx_groups\": $(grep -o 'calyx.group' "$out/removed-groups.calyx.mlir" 2>/dev/null | wc -l),"
      echo "    \"error\": \"$(tr '\n' ' ' < "$out/removed-groups.stderr" | sed 's/\\\"/\\\\\\\"/g')\""
      echo '  }'
      echo '  , "affine": {'
      echo "    \"exit_code\": $affine_status,"
      echo "    \"generated\": $(test -s "$out/affine.calyx.mlir" && echo true || echo false),"
      echo "    \"bytes\": $(wc -c < "$out/affine.calyx.mlir" 2>/dev/null || echo 0),"
      echo "    \"calyx_groups\": $(grep -o 'calyx.group' "$out/affine.calyx.mlir" 2>/dev/null | wc -l),"
      echo "    \"error\": \"$(tr '\n' ' ' < "$out/affine.stderr" | sed 's/\\\"/\\\\\\\"/g')\""
      echo '  }'
      echo '  , "affine_parallel": {'
      echo "    \"exit_code\": $affine_parallel_status,"
      echo "    \"generated\": $(test -s "$out/affine-parallel.calyx.mlir" && echo true || echo false),"
      echo "    \"bytes\": $(wc -c < "$out/affine-parallel.calyx.mlir" 2>/dev/null || echo 0),"
      echo "    \"calyx_groups\": $(grep -o 'calyx.group' "$out/affine-parallel.calyx.mlir" 2>/dev/null | wc -l),"
      echo "    \"error\": \"$(tr '\n' ' ' < "$out/affine-parallel.stderr" | sed 's/\\\"/\\\\\\\"/g')\""
      echo '  }'
      echo '  , "component_optimized": {'
      echo "    \"exit_code\": $component_status,"
      echo "    \"generated\": $(test -s "$out/component-optimized.calyx.mlir" && echo true || echo false),"
      echo "    \"bytes\": $(wc -c < "$out/component-optimized.calyx.mlir" 2>/dev/null || echo 0),"
      echo "    \"calyx_groups\": $(grep -o 'calyx.group' "$out/component-optimized.calyx.mlir" 2>/dev/null | wc -l),"
      echo "    \"error\": \"$(tr '\n' ' ' < "$out/component-optimized.stderr" | sed 's/\\\"/\\\\\\\"/g')\""
      echo '  }'
      echo '  , "banked_parallel": {'
      echo "    \"exit_code\": $banked_parallel_status,"
      echo "    \"generated\": $(test -s "$out/banked-parallel.calyx.mlir" && echo true || echo false),"
      echo "    \"bytes\": $(wc -c < "$out/banked-parallel.calyx.mlir" 2>/dev/null || echo 0),"
      echo "    \"calyx_groups\": $(grep -o 'calyx.group' "$out/banked-parallel.calyx.mlir" 2>/dev/null | wc -l),"
      echo "    \"error\": \"$(tr '\n' ' ' < "$out/banked-parallel.stderr" | sed 's/\\\"/\\\\\\\"/g')\""
      echo '  }'
      echo '  , "unparallelized": {'
      echo "    \"exit_code\": $unparallelized_status,"
      echo "    \"generated\": $(test -s "$out/unparallelized.calyx.mlir" && echo true || echo false),"
      echo "    \"bytes\": $(wc -c < "$out/unparallelized.calyx.mlir" 2>/dev/null || echo 0),"
      echo "    \"calyx_groups\": $(grep -o 'calyx.group' "$out/unparallelized.calyx.mlir" 2>/dev/null | wc -l),"
      echo "    \"error\": \"$(tr '\n' ' ' < "$out/unparallelized.stderr" | sed 's/\\\"/\\\\\\\"/g')\""
      echo '  }'
      echo '  , "affine_full": {'
      echo "    \"exit_code\": $affine_full_status,"
      echo "    \"generated\": $(test -s "$out/affine-full.calyx.mlir" && echo true || echo false),"
      echo "    \"bytes\": $(wc -c < "$out/affine-full.calyx.mlir" 2>/dev/null || echo 0),"
      echo "    \"calyx_groups\": $(grep -o 'calyx.group' "$out/affine-full.calyx.mlir" 2>/dev/null | wc -l),"
      echo "    \"error\": \"$(tr '\n' ' ' < "$out/affine-full.stderr" | sed 's/\\\"/\\\\\\\"/g')\""
      echo '  }'
      echo '  , "affine_complete": {'
      echo "    \"exit_code\": $affine_complete_status,"
      echo "    \"generated\": $(test -s "$out/affine-complete.calyx.mlir" && echo true || echo false),"
      echo "    \"bytes\": $(wc -c < "$out/affine-complete.calyx.mlir" 2>/dev/null || echo 0),"
      echo "    \"calyx_groups\": $(grep -o 'calyx.group' "$out/affine-complete.calyx.mlir" 2>/dev/null | wc -l),"
      echo "    \"error\": \"$(tr '\n' ' ' < "$out/affine-complete.stderr" | sed 's/\\\"/\\\\\\\"/g')\""
      echo '  }'
      echo '  , "gicm": {'
      echo "    \"exit_code\": $gicm_status,"
      echo "    \"generated\": $(test -s "$out/gicm.calyx.mlir" && echo true || echo false),"
      echo "    \"bytes\": $(wc -c < "$out/gicm.calyx.mlir" 2>/dev/null || echo 0),"
      echo "    \"calyx_groups\": $(grep -o 'calyx.group' "$out/gicm.calyx.mlir" 2>/dev/null | wc -l),"
      echo "    \"error\": \"$(tr '\n' ' ' < "$out/gicm.stderr" | sed 's/\\\"/\\\\\\\"/g')\""
      echo '  },'
      echo '  "no_comb_groups": {'
      echo "    \"exit_code\": $no_comb_status,"
      echo "    \"generated\": $(test -s "$out/no-comb-groups.calyx.mlir" && echo true || echo false),"
      echo "    \"bytes\": $(wc -c < "$out/no-comb-groups.calyx.mlir" 2>/dev/null || echo 0),"
      echo "    \"calyx_groups\": $(grep -o 'calyx.group' "$out/no-comb-groups.calyx.mlir" 2>/dev/null | wc -l),"
      echo "    \"error\": \"$(tr '\n' ' ' < "$out/no-comb-groups.stderr" | sed 's/\\\"/\\\\\\\"/g')\""
      echo '  }'
      echo '}'
    } > "$out/stats.json"
  '';
}
