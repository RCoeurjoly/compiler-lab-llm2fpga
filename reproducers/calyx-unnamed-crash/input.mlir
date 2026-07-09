module {
  memref.global "private" constant @__constant_1x1x1xf32 : memref<1xf32> = dense<1.000000e+00> {alignment = 64 : i64}
  memref.global "private" constant @__constant_2xf32_3 : memref<2xf32> = dense<0.000000e+00> {alignment = 64 : i64}
  memref.global "private" constant @__constant_8xf32_2 : memref<8xf32> = dense<0.000000e+00> {alignment = 64 : i64}
  memref.global "private" constant @__constant_2xf32_1 : memref<2xf32> = dense<0.000000e+00> {alignment = 64 : i64}
  memref.global "private" constant @__constant_2xf32_0 : memref<2xf32> = dense<0.000000e+00> {alignment = 64 : i64}
  memref.global "private" constant @__constant_8xf32 : memref<8xf32> = dense<0.000000e+00> {alignment = 64 : i64}
  memref.global "private" constant @__constant_2xf32 : memref<2xf32> = dense<0.000000e+00> {alignment = 64 : i64}
  func.func @main(%arg0: memref<4xi8>, %arg1: memref<4xi8>, %arg2: memref<4xi8>, %arg3: memref<4xi8>, %arg4: memref<16xi8>, %arg5: memref<16xi8>, %arg6: memref<4xi8>, %arg7: memref<4xi8>, %arg8: memref<4xi8>, %arg9: memref<4xi8>, %arg10: memref<16xi8>, %arg11: memref<16xi8>, %arg12: memref<64xi8>, %arg13: memref<i8>, %arg14: memref<i8>, %arg15: memref<i8>, %arg16: memref<i8>, %arg17: memref<i8>, %arg18: memref<i8>, %arg19: memref<i8>, %arg20: memref<i8>, %arg21: memref<i8>, %arg22: memref<i8>, %arg23: memref<i8>, %arg24: memref<i8>, %arg25: memref<i8>, %arg26: memref<i8>, %arg27: memref<i8>, %arg28: memref<i8>, %arg29: memref<f32>, %arg30: memref<2xi32>, %arg31: memref<2xi32>, %arg32: memref<i32>, %arg33: memref<i32>, %arg34: memref<i32>, %arg35: memref<i32>, %arg36: memref<i32>, %arg37: memref<i32>, %arg38: memref<i32>, %arg39: memref<i32>, %arg40: memref<i32>, %arg41: memref<f32>, %arg42: memref<2xi32>, %arg43: memref<2xi32>, %arg44: memref<i32>, %arg45: memref<i32>, %arg46: memref<i32>, %arg47: memref<i32>, %arg48: memref<i32>, %arg49: memref<i32>, %arg50: memref<i32>, %arg51: memref<i32>, %arg52: memref<i32>, %arg53: memref<f32>, %arg54: memref<2xi32>, %arg55: memref<2xi32>, %arg56: memref<i32>, %arg57: memref<i32>, %arg58: memref<i32>, %arg59: memref<i32>, %arg60: memref<i32>, %arg61: memref<i32>, %arg62: memref<i32>, %arg63: memref<i32>, %arg64: memref<i32>, %arg65: memref<f32>, %arg66: memref<2xi32>, %arg67: memref<2xi32>, %arg68: memref<i32>, %arg69: memref<i32>, %arg70: memref<i32>, %arg71: memref<i32>, %arg72: memref<i32>, %arg73: memref<i32>, %arg74: memref<i32>, %arg75: memref<i32>, %arg76: memref<i32>, %arg77: memref<64xi8>, %arg78: memref<f32>, %arg79: memref<8xi8>, %arg80: memref<f32>, %arg81: memref<f32>, %arg82: memref<2xi32>, %arg83: memref<2xi32>, %arg84: memref<i32>, %arg85: memref<i32>, %arg86: memref<i32>, %arg87: memref<i32>, %arg88: memref<i32>, %arg89: memref<i32>, %arg90: memref<i32>, %arg91: memref<i32>, %arg92: memref<i32>, %arg93: memref<1xi64>, %arg94: memref<32xi8>) {
    %cst = arith.constant 1.88735316E-6 : f32
    %cst_0 = arith.constant 1.43157638E-6 : f32
    %cst_1 = arith.constant 1.01008698E-6 : f32
    %cst_2 = arith.constant 1.19845674E-6 : f32
    %cst_3 = arith.constant 7.23551295E-7 : f32
    %c-1_i32 = arith.constant -1 : i32
    %c1_i32 = arith.constant 1 : i32
    %cst_4 = arith.constant -5.000000e-01 : f32
    %cst_5 = arith.constant 5.000000e-01 : f32
    %c8 = arith.constant 8 : index
    %c1 = arith.constant 1 : index
    %c2 = arith.constant 2 : index
    %c0 = arith.constant 0 : index
    %cst_6 = arith.constant -1.130000e+02 : f32
    %cst_7 = arith.constant 0.00310593424 : f32
    %cst_8 = arith.constant 1.2284579E-6 : f32
    %c-118_i32 = arith.constant -118 : i32
    %cst_9 = arith.constant -1.180000e+02 : f32
    %cst_10 = arith.constant 0.00310374703 : f32
    %cst_11 = arith.constant 6.55137455E-7 : f32
    %c-125_i32 = arith.constant -125 : i32
    %cst_12 = arith.constant -1.250000e+02 : f32
    %cst_13 = arith.constant 0.00310260523 : f32
    %c75_i32 = arith.constant 75 : i32
    %cst_14 = arith.constant 7.500000e+01 : f32
    %cst_15 = arith.constant 1.79526955E-6 : f32
    %c-124_i32 = arith.constant -124 : i32
    %cst_16 = arith.constant -1.240000e+02 : f32
    %cst_17 = arith.constant 0.00156447955 : f32
    %c-123_i32 = arith.constant -123 : i32
    %cst_18 = arith.constant -1.230000e+02 : f32
    %cst_19 = arith.constant 0.00196078443 : f32
    %c-119_i32 = arith.constant -119 : i32
    %cst_20 = arith.constant -1.190000e+02 : f32
    %cst_21 = arith.constant 0.00310161663 : f32
    %cst_22 = arith.constant 9.4023892E-7 : f32
    %cst_23 = arith.constant 2.4497835E-4 : f32
    %cst_24 = arith.constant 0.00391965359 : f32
    %cst_25 = arith.constant 0.00310091744 : f32
    %cst_26 = arith.constant 6.274510e-02 : f32
    %c74_i32 = arith.constant 74 : i32
    %cst_27 = arith.constant 7.400000e+01 : f32
    %c33_i32 = arith.constant 33 : i32
    %cst_28 = arith.constant 3.300000e+01 : f32
    %c66_i32 = arith.constant 66 : i32
    %cst_29 = arith.constant 0.654582202 : f32
    %cst_30 = arith.constant 6.600000e+01 : f32
    %c12_i32 = arith.constant 12 : i32
    %cst_31 = arith.constant 1.200000e+01 : f32
    %c127_i32 = arith.constant 127 : i32
    %cst_32 = arith.constant 0.294117659 : f32
    %cst_33 = arith.constant 2.45098054E-4 : f32
    %cst_34 = arith.constant 2.44140625E-4 : f32
    %c-128_i32 = arith.constant -128 : i32
    %c127_i8 = arith.constant 127 : i8
    %c-128_i8 = arith.constant -128 : i8
    %c7_i8 = arith.constant 7 : i8
    %c-8_i8 = arith.constant -8 : i8
    %c0_i64 = arith.constant 0 : i64
    %c32 = arith.constant 32 : index
    %cst_35 = arith.constant -1.280000e+02 : f32
    %cst_36 = arith.constant 1.270000e+02 : f32
    %c0_i32 = arith.constant 0 : i32
    %cst_37 = arith.constant 0.000000e+00 : f32
    %0 = memref.get_global @__constant_2xf32 : memref<2xf32>
    %1 = memref.get_global @__constant_8xf32 : memref<8xf32>
    %2 = memref.get_global @__constant_2xf32_0 : memref<2xf32>
    %3 = memref.get_global @__constant_2xf32_1 : memref<2xf32>
    %4 = memref.get_global @__constant_8xf32_2 : memref<8xf32>
    %5 = memref.get_global @__constant_2xf32_3 : memref<2xf32>
    %6 = memref.get_global @__constant_1x1x1xf32 : memref<1xf32>
    %alloc = memref.alloc() {alignment = 64 : i64} : memref<4xi8, strided<[1]>>
    %alloc_38 = memref.alloc() {alignment = 64 : i64} : memref<4xi8, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      scf.for %arg96 = %c0 to %c2 step %c1 {
        %316 = arith.muli %arg95, %c2 overflow<nsw> : index
        %317 = arith.addi %316, %arg96 : index
        %318 = memref.load %arg1[%317] : memref<4xi8>
        %319 = arith.cmpi slt, %318, %c-8_i8 : i8
        %320 = arith.select %319, %c-8_i8, %318 : i8
        %321 = arith.cmpi sge, %320, %c7_i8 : i8
        %322 = arith.select %321, %c7_i8, %320 : i8
        memref.store %322, %alloc_38[%317] : memref<4xi8, strided<[1]>>
      }
    }
    %alloc_39 = memref.alloc() {alignment = 64 : i64} : memref<4xi8, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      scf.for %arg96 = %c0 to %c2 step %c1 {
        %316 = arith.muli %arg95, %c2 overflow<nsw> : index
        %317 = arith.addi %316, %arg96 : index
        %318 = memref.load %arg3[%317] : memref<4xi8>
        %319 = arith.cmpi slt, %318, %c-8_i8 : i8
        %320 = arith.select %319, %c-8_i8, %318 : i8
        %321 = arith.cmpi sge, %320, %c7_i8 : i8
        %322 = arith.select %321, %c7_i8, %320 : i8
        memref.store %322, %alloc_39[%317] : memref<4xi8, strided<[1]>>
      }
    }
    %alloc_40 = memref.alloc() {alignment = 64 : i64} : memref<16xi8, strided<[1]>>
    scf.for %arg95 = %c0 to %c8 step %c1 {
      scf.for %arg96 = %c0 to %c2 step %c1 {
        %316 = arith.muli %arg95, %c2 overflow<nsw> : index
        %317 = arith.addi %316, %arg96 : index
        %318 = memref.load %arg4[%317] : memref<16xi8>
        %319 = arith.cmpi slt, %318, %c-8_i8 : i8
        %320 = arith.select %319, %c-8_i8, %318 : i8
        %321 = arith.cmpi sge, %320, %c7_i8 : i8
        %322 = arith.select %321, %c7_i8, %320 : i8
        memref.store %322, %alloc_40[%317] : memref<16xi8, strided<[1]>>
      }
    }
    %alloc_41 = memref.alloc() {alignment = 64 : i64} : memref<16xi8, strided<[1]>>
    %alloc_42 = memref.alloc() {alignment = 64 : i64} : memref<16xi8, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      scf.for %arg96 = %c0 to %c8 step %c1 {
        %316 = arith.muli %arg95, %c8 overflow<nsw> : index
        %317 = arith.addi %316, %arg96 : index
        %318 = memref.load %arg5[%317] : memref<16xi8>
        %319 = arith.cmpi slt, %318, %c-8_i8 : i8
        %320 = arith.select %319, %c-8_i8, %318 : i8
        %321 = arith.cmpi sge, %320, %c7_i8 : i8
        %322 = arith.select %321, %c7_i8, %320 : i8
        memref.store %322, %alloc_42[%317] : memref<16xi8, strided<[1]>>
      }
    }
    %alloc_43 = memref.alloc() {alignment = 64 : i64} : memref<4xi8, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      scf.for %arg96 = %c0 to %c2 step %c1 {
        %316 = arith.muli %arg95, %c2 overflow<nsw> : index
        %317 = arith.addi %316, %arg96 : index
        %318 = memref.load %arg7[%317] : memref<4xi8>
        %319 = arith.cmpi slt, %318, %c-8_i8 : i8
        %320 = arith.select %319, %c-8_i8, %318 : i8
        %321 = arith.cmpi sge, %320, %c7_i8 : i8
        %322 = arith.select %321, %c7_i8, %320 : i8
        memref.store %322, %alloc_43[%317] : memref<4xi8, strided<[1]>>
      }
    }
    %alloc_44 = memref.alloc() {alignment = 64 : i64} : memref<4xi8, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      scf.for %arg96 = %c0 to %c2 step %c1 {
        %316 = arith.muli %arg95, %c2 overflow<nsw> : index
        %317 = arith.addi %316, %arg96 : index
        %318 = memref.load %arg9[%317] : memref<4xi8>
        %319 = arith.cmpi slt, %318, %c-8_i8 : i8
        %320 = arith.select %319, %c-8_i8, %318 : i8
        %321 = arith.cmpi sge, %320, %c7_i8 : i8
        %322 = arith.select %321, %c7_i8, %320 : i8
        memref.store %322, %alloc_44[%317] : memref<4xi8, strided<[1]>>
      }
    }
    %alloc_45 = memref.alloc() {alignment = 64 : i64} : memref<16xi8, strided<[1]>>
    scf.for %arg95 = %c0 to %c8 step %c1 {
      scf.for %arg96 = %c0 to %c2 step %c1 {
        %316 = arith.muli %arg95, %c2 overflow<nsw> : index
        %317 = arith.addi %316, %arg96 : index
        %318 = memref.load %arg10[%317] : memref<16xi8>
        %319 = arith.cmpi slt, %318, %c-8_i8 : i8
        %320 = arith.select %319, %c-8_i8, %318 : i8
        %321 = arith.cmpi sge, %320, %c7_i8 : i8
        %322 = arith.select %321, %c7_i8, %320 : i8
        memref.store %322, %alloc_45[%317] : memref<16xi8, strided<[1]>>
      }
    }
    %alloc_46 = memref.alloc() {alignment = 64 : i64} : memref<16xi8, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      scf.for %arg96 = %c0 to %c8 step %c1 {
        %316 = arith.muli %arg95, %c8 overflow<nsw> : index
        %317 = arith.addi %316, %arg96 : index
        %318 = memref.load %arg11[%317] : memref<16xi8>
        %319 = arith.cmpi slt, %318, %c-8_i8 : i8
        %320 = arith.select %319, %c-8_i8, %318 : i8
        %321 = arith.cmpi sge, %320, %c7_i8 : i8
        %322 = arith.select %321, %c7_i8, %320 : i8
        memref.store %322, %alloc_46[%317] : memref<16xi8, strided<[1]>>
      }
    }
    %alloc_47 = memref.alloc() {alignment = 64 : i64} : memref<64xi8, strided<[1]>>
    scf.for %arg95 = %c0 to %c32 step %c1 {
      scf.for %arg96 = %c0 to %c2 step %c1 {
        %316 = arith.muli %arg95, %c2 overflow<nsw> : index
        %317 = arith.addi %316, %arg96 : index
        %318 = memref.load %arg12[%317] : memref<64xi8>
        %319 = arith.cmpi slt, %318, %c-8_i8 : i8
        %320 = arith.select %319, %c-8_i8, %318 : i8
        %321 = arith.cmpi sge, %320, %c7_i8 : i8
        %322 = arith.select %321, %c7_i8, %320 : i8
        memref.store %322, %alloc_47[%317] : memref<64xi8, strided<[1]>>
      }
    }
    %alloc_48 = memref.alloc() {alignment = 64 : i64} : memref<i8>
    %7 = memref.load %arg13[] : memref<i8>
    %8 = arith.cmpi slt, %7, %c-128_i8 : i8
    %9 = arith.select %8, %c-128_i8, %7 : i8
    %10 = arith.cmpi sge, %9, %c127_i8 : i8
    %11 = arith.select %10, %c127_i8, %9 : i8
    memref.store %11, %alloc_48[] : memref<i8>
    %alloc_49 = memref.alloc() {alignment = 64 : i64} : memref<f32>
    %alloc_50 = memref.alloc() {alignment = 64 : i64} : memref<f32>
    %12 = memref.load %alloc_48[] : memref<i8>
    %13 = arith.extsi %12 : i8 to i32
    %14 = arith.subi %13, %c-128_i32 : i32
    %15 = arith.sitofp %14 : i32 to f32
    %16 = arith.mulf %15, %cst_34 : f32
    memref.store %16, %alloc_50[] : memref<f32>
    %17 = memref.load %arg14[] : memref<i8>
    %18 = arith.cmpi slt, %17, %c-128_i8 : i8
    %19 = arith.select %18, %c-128_i8, %17 : i8
    %20 = arith.cmpi sge, %19, %c127_i8 : i8
    %21 = arith.select %20, %c127_i8, %19 : i8
    memref.store %21, %alloc_48[] : memref<i8>
    %22 = memref.load %alloc_48[] : memref<i8>
    %23 = arith.extsi %22 : i8 to i32
    %24 = arith.subi %23, %c-128_i32 : i32
    %25 = arith.sitofp %24 : i32 to f32
    %26 = arith.mulf %25, %cst_34 : f32
    memref.store %26, %alloc_49[] : memref<f32>
    %27 = memref.load %arg15[] : memref<i8>
    %28 = arith.cmpi slt, %27, %c-128_i8 : i8
    %29 = arith.select %28, %c-128_i8, %27 : i8
    %30 = arith.cmpi sge, %29, %c127_i8 : i8
    %31 = arith.select %30, %c127_i8, %29 : i8
    memref.store %31, %alloc_48[] : memref<i8>
    %alloc_51 = memref.alloc() {alignment = 64 : i64} : memref<f32>
    %32 = memref.load %alloc_48[] : memref<i8>
    %33 = arith.extsi %32 : i8 to i32
    %34 = arith.subi %33, %c-128_i32 : i32
    %35 = arith.sitofp %34 : i32 to f32
    %36 = arith.mulf %35, %cst_33 : f32
    memref.store %36, %alloc_51[] : memref<f32>
    %37 = memref.load %arg16[] : memref<i8>
    %38 = arith.cmpi slt, %37, %c-128_i8 : i8
    %39 = arith.select %38, %c-128_i8, %37 : i8
    %40 = arith.cmpi sge, %39, %c127_i8 : i8
    %41 = arith.select %40, %c127_i8, %39 : i8
    memref.store %41, %alloc_48[] : memref<i8>
    %alloc_52 = memref.alloc() {alignment = 64 : i64} : memref<f32>
    %42 = memref.load %alloc_48[] : memref<i8>
    %43 = arith.extsi %42 : i8 to i32
    %44 = arith.subi %43, %c-128_i32 : i32
    %45 = arith.sitofp %44 : i32 to f32
    %46 = arith.mulf %45, %cst_33 : f32
    memref.store %46, %alloc_52[] : memref<f32>
    %47 = memref.load %arg17[] : memref<i8>
    %48 = arith.cmpi slt, %47, %c-128_i8 : i8
    %49 = arith.select %48, %c-128_i8, %47 : i8
    %50 = arith.cmpi sge, %49, %c127_i8 : i8
    %51 = arith.select %50, %c127_i8, %49 : i8
    memref.store %51, %alloc_48[] : memref<i8>
    %alloc_53 = memref.alloc() {alignment = 64 : i64} : memref<f32>
    %52 = memref.load %alloc_48[] : memref<i8>
    %53 = arith.extsi %52 : i8 to i32
    %54 = arith.subi %53, %c-128_i32 : i32
    %55 = arith.sitofp %54 : i32 to f32
    %56 = arith.mulf %55, %cst_33 : f32
    memref.store %56, %alloc_53[] : memref<f32>
    %57 = memref.load %arg18[] : memref<i8>
    %58 = arith.cmpi slt, %57, %c-128_i8 : i8
    %59 = arith.select %58, %c-128_i8, %57 : i8
    %60 = arith.cmpi sge, %59, %c127_i8 : i8
    %61 = arith.select %60, %c127_i8, %59 : i8
    memref.store %61, %alloc_48[] : memref<i8>
    %alloc_54 = memref.alloc() {alignment = 64 : i64} : memref<f32>
    %62 = memref.load %alloc_48[] : memref<i8>
    %63 = arith.extsi %62 : i8 to i32
    %64 = arith.subi %63, %c-128_i32 : i32
    %65 = arith.sitofp %64 : i32 to f32
    %66 = arith.mulf %65, %cst_33 : f32
    memref.store %66, %alloc_54[] : memref<f32>
    %67 = memref.load %arg19[] : memref<i8>
    %68 = arith.cmpi slt, %67, %c-128_i8 : i8
    %69 = arith.select %68, %c-128_i8, %67 : i8
    %70 = arith.cmpi sge, %69, %c127_i8 : i8
    %71 = arith.select %70, %c127_i8, %69 : i8
    memref.store %71, %alloc_48[] : memref<i8>
    %alloc_55 = memref.alloc() {alignment = 64 : i64} : memref<f32>
    %72 = memref.load %alloc_48[] : memref<i8>
    %73 = arith.extsi %72 : i8 to i32
    %74 = arith.subi %73, %c-128_i32 : i32
    %75 = arith.sitofp %74 : i32 to f32
    %76 = arith.mulf %75, %cst_33 : f32
    memref.store %76, %alloc_55[] : memref<f32>
    %alloc_56 = memref.alloc() {alignment = 64 : i64} : memref<2xi8, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %arg93[%c0] : memref<1xi64>
      %317 = arith.index_cast %316 : i64 to index
      %318 = arith.muli %317, %c2 overflow<nsw> : index
      %319 = arith.addi %318, %arg95 : index
      %320 = memref.load %arg77[%319] : memref<64xi8>
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    %alloc_57 = memref.alloc() {alignment = 64 : i64} : memref<2xf32, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.sitofp %316 : i8 to f32
      memref.store %317, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_32 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_36 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.extsi %316 : i8 to i32
      %318 = arith.subi %317, %c127_i32 : i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.mulf %319, %cst_32 : f32
      memref.store %320, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = memref.load %alloc_50[] : memref<f32>
      %318 = arith.mulf %316, %317 : f32
      memref.store %318, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_34 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_31 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    %alloc_58 = memref.alloc() {alignment = 64 : i64} : memref<2xf32, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.extsi %316 : i8 to i32
      %318 = arith.subi %317, %c12_i32 : i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.mulf %319, %cst_34 : f32
      memref.store %320, %alloc_58[%arg95] : memref<2xf32, strided<[1]>>
    }
    %alloc_59 = memref.alloc() {alignment = 64 : i64} : memref<1xi64>
    memref.store %c0_i64, %alloc_59[%c0] : memref<1xi64>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_59[%c0] : memref<1xi64>
      %317 = arith.index_cast %316 : i64 to index
      %318 = arith.muli %317, %c2 overflow<nsw> : index
      %319 = arith.addi %318, %arg95 : index
      %320 = memref.load %arg79[%319] : memref<8xi8>
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.sitofp %316 : i8 to f32
      memref.store %317, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_29 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_30 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.extsi %316 : i8 to i32
      %318 = arith.subi %317, %c66_i32 : i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.mulf %319, %cst_29 : f32
      memref.store %320, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = memref.load %alloc_49[] : memref<f32>
      %318 = arith.mulf %316, %317 : f32
      memref.store %318, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_34 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_28 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.extsi %316 : i8 to i32
      %318 = arith.subi %317, %c33_i32 : i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.mulf %319, %cst_34 : f32
      memref.store %320, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_58[%arg95] : memref<2xf32, strided<[1]>>
      %317 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %318 = arith.addf %316, %317 : f32
      memref.store %318, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_34 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_27 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.extsi %316 : i8 to i32
      %318 = arith.subi %317, %c74_i32 : i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.mulf %319, %cst_34 : f32
      memref.store %320, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_34 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_27 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    %alloc_60 = memref.alloc() {alignment = 64 : i64} : memref<2xf32, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.extsi %316 : i8 to i32
      %318 = arith.subi %317, %c74_i32 : i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.mulf %319, %cst_34 : f32
      memref.store %320, %alloc_60[%arg95] : memref<2xf32, strided<[1]>>
    }
    %77 = memref.load %arg20[] : memref<i8>
    %78 = arith.cmpi slt, %77, %c-128_i8 : i8
    %79 = arith.select %78, %c-128_i8, %77 : i8
    %80 = arith.cmpi sge, %79, %c127_i8 : i8
    %81 = arith.select %80, %c127_i8, %79 : i8
    memref.store %81, %alloc_48[] : memref<i8>
    %82 = memref.load %alloc_48[] : memref<i8>
    %83 = arith.extsi %82 : i8 to i32
    %84 = arith.subi %83, %c-128_i32 : i32
    %85 = arith.sitofp %84 : i32 to f32
    %86 = arith.mulf %85, %cst_26 : f32
    memref.store %86, %alloc_49[] : memref<f32>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_60[%arg95] : memref<2xf32, strided<[1]>>
      %317 = memref.load %alloc_49[] : memref<f32>
      %318 = arith.mulf %316, %317 : f32
      memref.store %318, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_25 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_36 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.extsi %316 : i8 to i32
      %318 = arith.subi %317, %c127_i32 : i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.mulf %319, %cst_25 : f32
      memref.store %320, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.fptosi %316 : f32 to i32
      %318 = arith.sitofp %317 : i32 to f32
      %319 = arith.subf %316, %318 : f32
      %320 = arith.andi %317, %c1_i32 : i32
      %321 = arith.cmpi ne, %320, %c0_i32 : i32
      %322 = arith.cmpf ogt, %319, %cst_5 : f32
      %323 = arith.cmpf oeq, %319, %cst_5 : f32
      %324 = arith.andi %323, %321 : i1
      %325 = arith.ori %322, %324 : i1
      %326 = arith.cmpf olt, %319, %cst_4 : f32
      %327 = arith.cmpf oeq, %319, %cst_4 : f32
      %328 = arith.andi %327, %321 : i1
      %329 = arith.ori %326, %328 : i1
      %330 = arith.extui %325 : i1 to i32
      %331 = arith.select %329, %c-1_i32, %c0_i32 : i32
      %332 = arith.addi %317, %330 : i32
      %333 = arith.addi %332, %331 : i32
      %334 = arith.sitofp %333 : i32 to f32
      memref.store %334, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = memref.load %arg37[] : memref<i32>
      %318 = memref.load %arg38[] : memref<i32>
      %319 = arith.sitofp %317 : i32 to f32
      %320 = arith.cmpf ult, %316, %319 : f32
      %321 = arith.select %320, %319, %316 : f32
      %322 = arith.sitofp %318 : i32 to f32
      %323 = arith.cmpf ugt, %321, %322 : f32
      %324 = arith.select %323, %322, %321 : f32
      memref.store %324, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    %alloc_61 = memref.alloc() {alignment = 64 : i64} : memref<2xi32, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.fptosi %316 : f32 to i32
      memref.store %317, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    %alloc_62 = memref.alloc() {alignment = 64 : i64} : memref<1xi64, strided<[1]>>
    memref.store %c0_i64, %alloc_62[%c0] : memref<1xi64, strided<[1]>>
    %alloc_63 = memref.alloc() {alignment = 64 : i64} : memref<1xi64, strided<[1]>>
    %87 = memref.load %alloc_62[%c0] : memref<1xi64, strided<[1]>>
    memref.store %87, %alloc_63[%c0] : memref<1xi64, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %alloc_63[%c0] : memref<1xi64, strided<[1]>>
      %318 = arith.extsi %316 : i32 to i64
      %319 = arith.addi %318, %317 : i64
      memref.store %319, %alloc_63[%c0] : memref<1xi64, strided<[1]>>
    }
    %alloc_64 = memref.alloc() {alignment = 64 : i64} : memref<1xi32, strided<[1]>>
    %88 = memref.load %alloc_63[%c0] : memref<1xi64, strided<[1]>>
    %89 = arith.trunci %88 : i64 to i32
    memref.store %89, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %90 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %91 = memref.load %arg32[] : memref<i32>
    %92 = arith.shrsi %90, %91 : i32
    memref.store %92, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %alloc_65 = memref.alloc() {alignment = 64 : i64} : memref<2xi32, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
      %318 = arith.subi %316, %317 : i32
      memref.store %318, %alloc_65[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_65[%arg95] : memref<2xi32, strided<[1]>>
      %317 = arith.muli %316, %316 : i32
      memref.store %317, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    %alloc_66 = memref.alloc() {alignment = 64 : i64} : memref<1xi64, strided<[1]>>
    %93 = memref.load %alloc_62[%c0] : memref<1xi64, strided<[1]>>
    memref.store %93, %alloc_66[%c0] : memref<1xi64, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %alloc_66[%c0] : memref<1xi64, strided<[1]>>
      %318 = arith.extsi %316 : i32 to i64
      %319 = arith.addi %318, %317 : i64
      memref.store %319, %alloc_66[%c0] : memref<1xi64, strided<[1]>>
    }
    %94 = memref.load %alloc_66[%c0] : memref<1xi64, strided<[1]>>
    %95 = arith.trunci %94 : i64 to i32
    memref.store %95, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %96 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %97 = memref.load %arg32[] : memref<i32>
    %98 = arith.shrsi %96, %97 : i32
    memref.store %98, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %99 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %100 = memref.load %arg39[] : memref<i32>
    %101 = arith.cmpi sgt, %99, %100 : i32
    %102 = arith.select %101, %99, %100 : i32
    memref.store %102, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %103 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %104 = memref.load %arg40[] : memref<i32>
    %105 = arith.cmpi slt, %103, %104 : i32
    %106 = arith.select %105, %103, %104 : i32
    memref.store %106, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %107 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %108 = memref.load %arg33[] : memref<i32>
    %109 = arith.shrsi %107, %108 : i32
    memref.store %109, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %110 = memref.load %arg35[] : memref<i32>
    %111 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %112 = arith.subi %110, %111 : i32
    memref.store %112, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %113 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %114 = memref.load %arg36[] : memref<i32>
    %115 = arith.cmpi sgt, %113, %114 : i32
    %116 = arith.select %115, %113, %114 : i32
    memref.store %116, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_65[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
      %318 = arith.muli %316, %317 : i32
      memref.store %318, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %arg34[] : memref<i32>
      %318 = arith.shrsi %316, %317 : i32
      memref.store %318, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %arg30[%arg95] : memref<2xi32>
      %318 = arith.muli %316, %317 : i32
      memref.store %318, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %arg34[] : memref<i32>
      %318 = arith.shrsi %316, %317 : i32
      memref.store %318, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %arg31[%arg95] : memref<2xi32>
      %318 = arith.addi %316, %317 : i32
      memref.store %318, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %arg37[] : memref<i32>
      %318 = arith.cmpi sgt, %316, %317 : i32
      %319 = arith.select %318, %316, %317 : i32
      memref.store %319, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %arg38[] : memref<i32>
      %318 = arith.cmpi slt, %316, %317 : i32
      %319 = arith.select %318, %316, %317 : i32
      memref.store %319, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = arith.sitofp %316 : i32 to f32
      memref.store %317, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_24 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_35 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.extsi %316 : i8 to i32
      %318 = arith.subi %317, %c-128_i32 : i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.mulf %319, %cst_24 : f32
      memref.store %320, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = memref.load %alloc_51[] : memref<f32>
      %318 = arith.mulf %316, %317 : f32
      memref.store %318, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_23 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_35 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      scf.for %arg96 = %c0 to %c2 step %c1 {
        %316 = arith.muli %arg96, %c2 overflow<nsw> : index
        %317 = arith.addi %316, %arg95 : index
        %318 = memref.load %alloc_38[%317] : memref<4xi8, strided<[1]>>
        %319 = arith.muli %arg95, %c2 overflow<nsw> : index
        %320 = arith.addi %319, %arg96 : index
        memref.store %318, %alloc[%320] : memref<4xi8, strided<[1]>>
      }
    }
    %alloc_67 = memref.alloc() {alignment = 64 : i64} : memref<4xi8, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      scf.for %arg96 = %c0 to %c2 step %c1 {
        %316 = arith.muli %arg95, %c2 overflow<nsw> : index
        %317 = arith.addi %316, %arg96 : index
        %318 = memref.load %alloc[%317] : memref<4xi8, strided<[1]>>
        memref.store %318, %alloc_67[%317] : memref<4xi8, strided<[1]>>
      }
    }
    %alloc_68 = memref.alloc() {alignment = 64 : i64} : memref<2xi32, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      memref.store %c0_i32, %alloc_68[%arg95] : memref<2xi32, strided<[1]>>
    }
    %alloc_69 = memref.alloc() {alignment = 64 : i64} : memref<2xi32, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_68[%arg95] : memref<2xi32, strided<[1]>>
      memref.store %316, %alloc_69[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      scf.for %arg96 = %c0 to %c2 step %c1 {
        %316 = memref.load %alloc_56[%arg96] : memref<2xi8, strided<[1]>>
        %317 = arith.muli %arg96, %c2 overflow<nsw> : index
        %318 = arith.addi %317, %arg95 : index
        %319 = memref.load %alloc_67[%318] : memref<4xi8, strided<[1]>>
        %320 = memref.load %alloc_69[%arg95] : memref<2xi32, strided<[1]>>
        %321 = arith.extsi %316 : i8 to i32
        %322 = arith.subi %321, %c-128_i32 : i32
        %323 = arith.extsi %319 : i8 to i32
        %324 = arith.muli %322, %323 : i32
        %325 = arith.addi %320, %324 : i32
        memref.store %325, %alloc_69[%arg95] : memref<2xi32, strided<[1]>>
      }
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_69[%arg95] : memref<2xi32, strided<[1]>>
      %317 = arith.sitofp %316 : i32 to f32
      %318 = arith.mulf %317, %cst_3 : f32
      memref.store %318, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_34 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_35 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.extsi %316 : i8 to i32
      %318 = arith.subi %317, %c-128_i32 : i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.mulf %319, %cst_34 : f32
      memref.store %320, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    %alloc_70 = memref.alloc() {alignment = 64 : i64} : memref<2xi8, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_34 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_35 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_70[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_70[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_70[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_70[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_70[%arg95] : memref<2xi8, strided<[1]>>
    }
    %alloc_71 = memref.alloc() {alignment = 64 : i64} : memref<2xf32, strided<[1]>>
    %alloc_72 = memref.alloc() {alignment = 64 : i64} : memref<2xf32, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_70[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.extsi %316 : i8 to i32
      %318 = arith.subi %317, %c-128_i32 : i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.mulf %319, %cst_34 : f32
      memref.store %320, %alloc_72[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_72[%arg95] : memref<2xf32, strided<[1]>>
      memref.store %316, %alloc_71[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_71[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_34 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_35 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_70[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_70[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_70[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_70[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_70[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_70[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.extsi %316 : i8 to i32
      %318 = arith.subi %317, %c-128_i32 : i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.mulf %319, %cst_34 : f32
      memref.store %320, %alloc_71[%arg95] : memref<2xf32, strided<[1]>>
    }
    %alloc_73 = memref.alloc() {alignment = 64 : i64} : memref<2xf32, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      memref.store %cst_37, %alloc_73[%arg95] : memref<2xf32, strided<[1]>>
    }
    %alloc_74 = memref.alloc() {alignment = 64 : i64} : memref<2xf32, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_73[%arg95] : memref<2xf32, strided<[1]>>
      memref.store %316, %alloc_74[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %6[%c0] : memref<1xf32>
      %317 = memref.load %alloc_71[%arg95] : memref<2xf32, strided<[1]>>
      %318 = memref.load %alloc_74[%arg95] : memref<2xf32, strided<[1]>>
      %319 = arith.mulf %316, %317 : f32
      %320 = arith.addf %318, %319 : f32
      memref.store %320, %alloc_74[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_74[%arg95] : memref<2xf32, strided<[1]>>
      memref.store %316, %alloc_71[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_71[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_34 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_35 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      scf.for %arg96 = %c0 to %c2 step %c1 {
        %316 = arith.muli %arg96, %c2 overflow<nsw> : index
        %317 = arith.addi %316, %arg95 : index
        %318 = memref.load %alloc_39[%317] : memref<4xi8, strided<[1]>>
        %319 = arith.muli %arg95, %c2 overflow<nsw> : index
        %320 = arith.addi %319, %arg96 : index
        memref.store %318, %alloc[%320] : memref<4xi8, strided<[1]>>
      }
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      scf.for %arg96 = %c0 to %c2 step %c1 {
        %316 = arith.muli %arg95, %c2 overflow<nsw> : index
        %317 = arith.addi %316, %arg96 : index
        %318 = memref.load %alloc[%317] : memref<4xi8, strided<[1]>>
        memref.store %318, %alloc_67[%317] : memref<4xi8, strided<[1]>>
      }
    }
    %alloc_75 = memref.alloc() {alignment = 64 : i64} : memref<2xi32, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_68[%arg95] : memref<2xi32, strided<[1]>>
      memref.store %316, %alloc_75[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      scf.for %arg96 = %c0 to %c2 step %c1 {
        %316 = memref.load %alloc_56[%arg96] : memref<2xi8, strided<[1]>>
        %317 = arith.muli %arg96, %c2 overflow<nsw> : index
        %318 = arith.addi %317, %arg95 : index
        %319 = memref.load %alloc_67[%318] : memref<4xi8, strided<[1]>>
        %320 = memref.load %alloc_75[%arg95] : memref<2xi32, strided<[1]>>
        %321 = arith.extsi %316 : i8 to i32
        %322 = arith.subi %321, %c-128_i32 : i32
        %323 = arith.extsi %319 : i8 to i32
        %324 = arith.muli %322, %323 : i32
        %325 = arith.addi %320, %324 : i32
        memref.store %325, %alloc_75[%arg95] : memref<2xi32, strided<[1]>>
      }
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_75[%arg95] : memref<2xi32, strided<[1]>>
      %317 = arith.sitofp %316 : i32 to f32
      %318 = arith.mulf %317, %cst_22 : f32
      memref.store %318, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = memref.load %5[%arg95] : memref<2xf32>
      %318 = arith.addf %316, %317 : f32
      memref.store %318, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_34 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_35 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.extsi %316 : i8 to i32
      %318 = arith.subi %317, %c-128_i32 : i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.mulf %319, %cst_34 : f32
      memref.store %320, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_34 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_35 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.extsi %316 : i8 to i32
      %318 = arith.subi %317, %c-128_i32 : i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.mulf %319, %cst_34 : f32
      memref.store %320, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = memref.load %alloc_60[%arg95] : memref<2xf32, strided<[1]>>
      %318 = arith.addf %316, %317 : f32
      memref.store %318, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_34 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_27 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    %alloc_76 = memref.alloc() {alignment = 64 : i64} : memref<2xf32, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.extsi %316 : i8 to i32
      %318 = arith.subi %317, %c74_i32 : i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.mulf %319, %cst_34 : f32
      memref.store %320, %alloc_76[%arg95] : memref<2xf32, strided<[1]>>
    }
    %117 = memref.load %arg21[] : memref<i8>
    %118 = arith.cmpi slt, %117, %c-128_i8 : i8
    %119 = arith.select %118, %c-128_i8, %117 : i8
    %120 = arith.cmpi sge, %119, %c127_i8 : i8
    %121 = arith.select %120, %c127_i8, %119 : i8
    memref.store %121, %alloc_48[] : memref<i8>
    %122 = memref.load %alloc_48[] : memref<i8>
    %123 = arith.extsi %122 : i8 to i32
    %124 = arith.subi %123, %c-128_i32 : i32
    %125 = arith.sitofp %124 : i32 to f32
    %126 = arith.mulf %125, %cst_26 : f32
    memref.store %126, %alloc_49[] : memref<f32>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_76[%arg95] : memref<2xf32, strided<[1]>>
      %317 = memref.load %alloc_49[] : memref<f32>
      %318 = arith.mulf %316, %317 : f32
      memref.store %318, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_21 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_36 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.extsi %316 : i8 to i32
      %318 = arith.subi %317, %c127_i32 : i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.mulf %319, %cst_21 : f32
      memref.store %320, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.fptosi %316 : f32 to i32
      %318 = arith.sitofp %317 : i32 to f32
      %319 = arith.subf %316, %318 : f32
      %320 = arith.andi %317, %c1_i32 : i32
      %321 = arith.cmpi ne, %320, %c0_i32 : i32
      %322 = arith.cmpf ogt, %319, %cst_5 : f32
      %323 = arith.cmpf oeq, %319, %cst_5 : f32
      %324 = arith.andi %323, %321 : i1
      %325 = arith.ori %322, %324 : i1
      %326 = arith.cmpf olt, %319, %cst_4 : f32
      %327 = arith.cmpf oeq, %319, %cst_4 : f32
      %328 = arith.andi %327, %321 : i1
      %329 = arith.ori %326, %328 : i1
      %330 = arith.extui %325 : i1 to i32
      %331 = arith.select %329, %c-1_i32, %c0_i32 : i32
      %332 = arith.addi %317, %330 : i32
      %333 = arith.addi %332, %331 : i32
      %334 = arith.sitofp %333 : i32 to f32
      memref.store %334, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = memref.load %arg49[] : memref<i32>
      %318 = memref.load %arg50[] : memref<i32>
      %319 = arith.sitofp %317 : i32 to f32
      %320 = arith.cmpf ult, %316, %319 : f32
      %321 = arith.select %320, %319, %316 : f32
      %322 = arith.sitofp %318 : i32 to f32
      %323 = arith.cmpf ugt, %321, %322 : f32
      %324 = arith.select %323, %322, %321 : f32
      memref.store %324, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.fptosi %316 : f32 to i32
      memref.store %317, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    %alloc_77 = memref.alloc() {alignment = 64 : i64} : memref<1xi64, strided<[1]>>
    %127 = memref.load %alloc_62[%c0] : memref<1xi64, strided<[1]>>
    memref.store %127, %alloc_77[%c0] : memref<1xi64, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %alloc_77[%c0] : memref<1xi64, strided<[1]>>
      %318 = arith.extsi %316 : i32 to i64
      %319 = arith.addi %318, %317 : i64
      memref.store %319, %alloc_77[%c0] : memref<1xi64, strided<[1]>>
    }
    %128 = memref.load %alloc_77[%c0] : memref<1xi64, strided<[1]>>
    %129 = arith.trunci %128 : i64 to i32
    memref.store %129, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %130 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %131 = memref.load %arg44[] : memref<i32>
    %132 = arith.shrsi %130, %131 : i32
    memref.store %132, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %alloc_78 = memref.alloc() {alignment = 64 : i64} : memref<2xi32, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
      %318 = arith.subi %316, %317 : i32
      memref.store %318, %alloc_78[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_78[%arg95] : memref<2xi32, strided<[1]>>
      %317 = arith.muli %316, %316 : i32
      memref.store %317, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    %alloc_79 = memref.alloc() {alignment = 64 : i64} : memref<1xi64, strided<[1]>>
    %133 = memref.load %alloc_62[%c0] : memref<1xi64, strided<[1]>>
    memref.store %133, %alloc_79[%c0] : memref<1xi64, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %alloc_79[%c0] : memref<1xi64, strided<[1]>>
      %318 = arith.extsi %316 : i32 to i64
      %319 = arith.addi %318, %317 : i64
      memref.store %319, %alloc_79[%c0] : memref<1xi64, strided<[1]>>
    }
    %134 = memref.load %alloc_79[%c0] : memref<1xi64, strided<[1]>>
    %135 = arith.trunci %134 : i64 to i32
    memref.store %135, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %136 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %137 = memref.load %arg44[] : memref<i32>
    %138 = arith.shrsi %136, %137 : i32
    memref.store %138, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %139 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %140 = memref.load %arg51[] : memref<i32>
    %141 = arith.cmpi sgt, %139, %140 : i32
    %142 = arith.select %141, %139, %140 : i32
    memref.store %142, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %143 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %144 = memref.load %arg52[] : memref<i32>
    %145 = arith.cmpi slt, %143, %144 : i32
    %146 = arith.select %145, %143, %144 : i32
    memref.store %146, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %147 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %148 = memref.load %arg45[] : memref<i32>
    %149 = arith.shrsi %147, %148 : i32
    memref.store %149, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %150 = memref.load %arg47[] : memref<i32>
    %151 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %152 = arith.subi %150, %151 : i32
    memref.store %152, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %153 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %154 = memref.load %arg48[] : memref<i32>
    %155 = arith.cmpi sgt, %153, %154 : i32
    %156 = arith.select %155, %153, %154 : i32
    memref.store %156, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_78[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
      %318 = arith.muli %316, %317 : i32
      memref.store %318, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %arg46[] : memref<i32>
      %318 = arith.shrsi %316, %317 : i32
      memref.store %318, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %arg42[%arg95] : memref<2xi32>
      %318 = arith.muli %316, %317 : i32
      memref.store %318, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %arg46[] : memref<i32>
      %318 = arith.shrsi %316, %317 : i32
      memref.store %318, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %arg43[%arg95] : memref<2xi32>
      %318 = arith.addi %316, %317 : i32
      memref.store %318, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %arg49[] : memref<i32>
      %318 = arith.cmpi sgt, %316, %317 : i32
      %319 = arith.select %318, %316, %317 : i32
      memref.store %319, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %arg50[] : memref<i32>
      %318 = arith.cmpi slt, %316, %317 : i32
      %319 = arith.select %318, %316, %317 : i32
      memref.store %319, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = arith.sitofp %316 : i32 to f32
      memref.store %317, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_24 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_35 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.extsi %316 : i8 to i32
      %318 = arith.subi %317, %c-128_i32 : i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.mulf %319, %cst_24 : f32
      memref.store %320, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = memref.load %alloc_52[] : memref<f32>
      %318 = arith.mulf %316, %317 : f32
      memref.store %318, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_23 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_35 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      scf.for %arg96 = %c0 to %c8 step %c1 {
        %316 = arith.muli %arg96, %c2 overflow<nsw> : index
        %317 = arith.addi %316, %arg95 : index
        %318 = memref.load %alloc_40[%317] : memref<16xi8, strided<[1]>>
        %319 = arith.muli %arg95, %c8 overflow<nsw> : index
        %320 = arith.addi %319, %arg96 : index
        memref.store %318, %alloc_41[%320] : memref<16xi8, strided<[1]>>
      }
    }
    %alloc_80 = memref.alloc() {alignment = 64 : i64} : memref<16xi8, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      scf.for %arg96 = %c0 to %c8 step %c1 {
        %316 = arith.muli %arg95, %c8 overflow<nsw> : index
        %317 = arith.addi %316, %arg96 : index
        %318 = memref.load %alloc_41[%317] : memref<16xi8, strided<[1]>>
        memref.store %318, %alloc_80[%317] : memref<16xi8, strided<[1]>>
      }
    }
    %alloc_81 = memref.alloc() {alignment = 64 : i64} : memref<8xi32, strided<[1]>>
    scf.for %arg95 = %c0 to %c8 step %c1 {
      memref.store %c0_i32, %alloc_81[%arg95] : memref<8xi32, strided<[1]>>
    }
    %alloc_82 = memref.alloc() {alignment = 64 : i64} : memref<8xi32, strided<[1]>>
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_81[%arg95] : memref<8xi32, strided<[1]>>
      memref.store %316, %alloc_82[%arg95] : memref<8xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      scf.for %arg96 = %c0 to %c2 step %c1 {
        %316 = memref.load %alloc_56[%arg96] : memref<2xi8, strided<[1]>>
        %317 = arith.muli %arg96, %c8 overflow<nsw> : index
        %318 = arith.addi %317, %arg95 : index
        %319 = memref.load %alloc_80[%318] : memref<16xi8, strided<[1]>>
        %320 = memref.load %alloc_82[%arg95] : memref<8xi32, strided<[1]>>
        %321 = arith.extsi %316 : i8 to i32
        %322 = arith.subi %321, %c-128_i32 : i32
        %323 = arith.extsi %319 : i8 to i32
        %324 = arith.muli %322, %323 : i32
        %325 = arith.addi %320, %324 : i32
        memref.store %325, %alloc_82[%arg95] : memref<8xi32, strided<[1]>>
      }
    }
    %alloc_83 = memref.alloc() {alignment = 64 : i64} : memref<8xf32, strided<[1]>>
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_82[%arg95] : memref<8xi32, strided<[1]>>
      %317 = arith.sitofp %316 : i32 to f32
      %318 = arith.mulf %317, %cst_2 : f32
      memref.store %318, %alloc_83[%arg95] : memref<8xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_83[%arg95] : memref<8xf32, strided<[1]>>
      %317 = memref.load %4[%arg95] : memref<8xf32>
      %318 = arith.addf %316, %317 : f32
      memref.store %318, %alloc_83[%arg95] : memref<8xf32, strided<[1]>>
    }
    %alloc_84 = memref.alloc() {alignment = 64 : i64} : memref<8xi8, strided<[1]>>
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_83[%arg95] : memref<8xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_34 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_20 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
    }
    %alloc_85 = memref.alloc() {alignment = 64 : i64} : memref<8xf32, strided<[1]>>
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
      %317 = arith.extsi %316 : i8 to i32
      %318 = arith.subi %317, %c-119_i32 : i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.mulf %319, %cst_34 : f32
      memref.store %320, %alloc_85[%arg95] : memref<8xf32, strided<[1]>>
    }
    %157 = memref.load %arg22[] : memref<i8>
    %158 = arith.cmpi slt, %157, %c-128_i8 : i8
    %159 = arith.select %158, %c-128_i8, %157 : i8
    %160 = arith.cmpi sge, %159, %c127_i8 : i8
    %161 = arith.select %160, %c127_i8, %159 : i8
    memref.store %161, %alloc_48[] : memref<i8>
    %162 = memref.load %alloc_48[] : memref<i8>
    %163 = arith.extsi %162 : i8 to i32
    %164 = arith.subi %163, %c-128_i32 : i32
    %165 = arith.sitofp %164 : i32 to f32
    %166 = arith.mulf %165, %cst_19 : f32
    memref.store %166, %alloc_49[] : memref<f32>
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_85[%arg95] : memref<8xf32, strided<[1]>>
      %317 = memref.load %alloc_49[] : memref<f32>
      %318 = arith.mulf %316, %317 : f32
      memref.store %318, %alloc_83[%arg95] : memref<8xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_83[%arg95] : memref<8xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_34 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_18 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
    }
    %alloc_86 = memref.alloc() {alignment = 64 : i64} : memref<8xf32, strided<[1]>>
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
      %317 = arith.extsi %316 : i8 to i32
      %318 = arith.subi %317, %c-123_i32 : i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.mulf %319, %cst_34 : f32
      memref.store %320, %alloc_86[%arg95] : memref<8xf32, strided<[1]>>
    }
    %167 = memref.load %arg23[] : memref<i8>
    %168 = arith.cmpi slt, %167, %c-128_i8 : i8
    %169 = arith.select %168, %c-128_i8, %167 : i8
    %170 = arith.cmpi sge, %169, %c127_i8 : i8
    %171 = arith.select %170, %c127_i8, %169 : i8
    memref.store %171, %alloc_48[] : memref<i8>
    %172 = memref.load %alloc_48[] : memref<i8>
    %173 = arith.extsi %172 : i8 to i32
    %174 = arith.subi %173, %c-128_i32 : i32
    %175 = arith.sitofp %174 : i32 to f32
    %176 = arith.mulf %175, %cst_17 : f32
    memref.store %176, %alloc_49[] : memref<f32>
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_85[%arg95] : memref<8xf32, strided<[1]>>
      %317 = memref.load %alloc_49[] : memref<f32>
      %318 = arith.mulf %316, %317 : f32
      memref.store %318, %alloc_83[%arg95] : memref<8xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_83[%arg95] : memref<8xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_34 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_16 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
      %317 = arith.extsi %316 : i8 to i32
      %318 = arith.subi %317, %c-124_i32 : i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.mulf %319, %cst_34 : f32
      memref.store %320, %alloc_83[%arg95] : memref<8xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_83[%arg95] : memref<8xf32, strided<[1]>>
      %317 = memref.load %alloc_85[%arg95] : memref<8xf32, strided<[1]>>
      %318 = arith.mulf %316, %317 : f32
      memref.store %318, %alloc_83[%arg95] : memref<8xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_83[%arg95] : memref<8xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_34 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_35 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
      %317 = arith.extsi %316 : i8 to i32
      %318 = arith.subi %317, %c-128_i32 : i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.mulf %319, %cst_34 : f32
      memref.store %320, %alloc_83[%arg95] : memref<8xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_86[%arg95] : memref<8xf32, strided<[1]>>
      %317 = memref.load %alloc_83[%arg95] : memref<8xf32, strided<[1]>>
      %318 = arith.addf %316, %317 : f32
      memref.store %318, %alloc_83[%arg95] : memref<8xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_83[%arg95] : memref<8xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_34 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_18 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      scf.for %arg96 = %c0 to %c2 step %c1 {
        %316 = arith.muli %arg96, %c8 overflow<nsw> : index
        %317 = arith.addi %316, %arg95 : index
        %318 = memref.load %alloc_42[%317] : memref<16xi8, strided<[1]>>
        %319 = arith.muli %arg95, %c2 overflow<nsw> : index
        %320 = arith.addi %319, %arg96 : index
        memref.store %318, %alloc_40[%320] : memref<16xi8, strided<[1]>>
      }
    }
    %alloc_87 = memref.alloc() {alignment = 64 : i64} : memref<16xi8, strided<[1]>>
    scf.for %arg95 = %c0 to %c8 step %c1 {
      scf.for %arg96 = %c0 to %c2 step %c1 {
        %316 = arith.muli %arg95, %c2 overflow<nsw> : index
        %317 = arith.addi %316, %arg96 : index
        %318 = memref.load %alloc_40[%317] : memref<16xi8, strided<[1]>>
        memref.store %318, %alloc_87[%317] : memref<16xi8, strided<[1]>>
      }
    }
    %alloc_88 = memref.alloc() {alignment = 64 : i64} : memref<2xi32, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_68[%arg95] : memref<2xi32, strided<[1]>>
      memref.store %316, %alloc_88[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      scf.for %arg96 = %c0 to %c8 step %c1 {
        %316 = memref.load %alloc_84[%arg96] : memref<8xi8, strided<[1]>>
        %317 = arith.muli %arg96, %c2 overflow<nsw> : index
        %318 = arith.addi %317, %arg95 : index
        %319 = memref.load %alloc_87[%318] : memref<16xi8, strided<[1]>>
        %320 = memref.load %alloc_88[%arg95] : memref<2xi32, strided<[1]>>
        %321 = arith.extsi %316 : i8 to i32
        %322 = arith.subi %321, %c-123_i32 : i32
        %323 = arith.extsi %319 : i8 to i32
        %324 = arith.muli %322, %323 : i32
        %325 = arith.addi %320, %324 : i32
        memref.store %325, %alloc_88[%arg95] : memref<2xi32, strided<[1]>>
      }
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_88[%arg95] : memref<2xi32, strided<[1]>>
      %317 = arith.sitofp %316 : i32 to f32
      %318 = arith.mulf %317, %cst_15 : f32
      memref.store %318, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = memref.load %3[%arg95] : memref<2xf32>
      %318 = arith.addf %316, %317 : f32
      memref.store %318, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_34 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_35 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.extsi %316 : i8 to i32
      %318 = arith.subi %317, %c-128_i32 : i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.mulf %319, %cst_34 : f32
      memref.store %320, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_34 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_35 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.extsi %316 : i8 to i32
      %318 = arith.subi %317, %c-128_i32 : i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.mulf %319, %cst_34 : f32
      memref.store %320, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_76[%arg95] : memref<2xf32, strided<[1]>>
      %317 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %318 = arith.addf %316, %317 : f32
      memref.store %318, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_34 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_14 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    %alloc_89 = memref.alloc() {alignment = 64 : i64} : memref<2xf32, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.extsi %316 : i8 to i32
      %318 = arith.subi %317, %c75_i32 : i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.mulf %319, %cst_34 : f32
      memref.store %320, %alloc_89[%arg95] : memref<2xf32, strided<[1]>>
    }
    %177 = memref.load %arg24[] : memref<i8>
    %178 = arith.cmpi slt, %177, %c-128_i8 : i8
    %179 = arith.select %178, %c-128_i8, %177 : i8
    %180 = arith.cmpi sge, %179, %c127_i8 : i8
    %181 = arith.select %180, %c127_i8, %179 : i8
    memref.store %181, %alloc_48[] : memref<i8>
    %182 = memref.load %alloc_48[] : memref<i8>
    %183 = arith.extsi %182 : i8 to i32
    %184 = arith.subi %183, %c-128_i32 : i32
    %185 = arith.sitofp %184 : i32 to f32
    %186 = arith.mulf %185, %cst_26 : f32
    memref.store %186, %alloc_49[] : memref<f32>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_89[%arg95] : memref<2xf32, strided<[1]>>
      %317 = memref.load %alloc_49[] : memref<f32>
      %318 = arith.mulf %316, %317 : f32
      memref.store %318, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_13 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_36 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.extsi %316 : i8 to i32
      %318 = arith.subi %317, %c127_i32 : i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.mulf %319, %cst_13 : f32
      memref.store %320, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.fptosi %316 : f32 to i32
      %318 = arith.sitofp %317 : i32 to f32
      %319 = arith.subf %316, %318 : f32
      %320 = arith.andi %317, %c1_i32 : i32
      %321 = arith.cmpi ne, %320, %c0_i32 : i32
      %322 = arith.cmpf ogt, %319, %cst_5 : f32
      %323 = arith.cmpf oeq, %319, %cst_5 : f32
      %324 = arith.andi %323, %321 : i1
      %325 = arith.ori %322, %324 : i1
      %326 = arith.cmpf olt, %319, %cst_4 : f32
      %327 = arith.cmpf oeq, %319, %cst_4 : f32
      %328 = arith.andi %327, %321 : i1
      %329 = arith.ori %326, %328 : i1
      %330 = arith.extui %325 : i1 to i32
      %331 = arith.select %329, %c-1_i32, %c0_i32 : i32
      %332 = arith.addi %317, %330 : i32
      %333 = arith.addi %332, %331 : i32
      %334 = arith.sitofp %333 : i32 to f32
      memref.store %334, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = memref.load %arg61[] : memref<i32>
      %318 = memref.load %arg62[] : memref<i32>
      %319 = arith.sitofp %317 : i32 to f32
      %320 = arith.cmpf ult, %316, %319 : f32
      %321 = arith.select %320, %319, %316 : f32
      %322 = arith.sitofp %318 : i32 to f32
      %323 = arith.cmpf ugt, %321, %322 : f32
      %324 = arith.select %323, %322, %321 : f32
      memref.store %324, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.fptosi %316 : f32 to i32
      memref.store %317, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    %alloc_90 = memref.alloc() {alignment = 64 : i64} : memref<1xi64, strided<[1]>>
    %187 = memref.load %alloc_62[%c0] : memref<1xi64, strided<[1]>>
    memref.store %187, %alloc_90[%c0] : memref<1xi64, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %alloc_90[%c0] : memref<1xi64, strided<[1]>>
      %318 = arith.extsi %316 : i32 to i64
      %319 = arith.addi %318, %317 : i64
      memref.store %319, %alloc_90[%c0] : memref<1xi64, strided<[1]>>
    }
    %188 = memref.load %alloc_90[%c0] : memref<1xi64, strided<[1]>>
    %189 = arith.trunci %188 : i64 to i32
    memref.store %189, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %190 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %191 = memref.load %arg56[] : memref<i32>
    %192 = arith.shrsi %190, %191 : i32
    memref.store %192, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %alloc_91 = memref.alloc() {alignment = 64 : i64} : memref<2xi32, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
      %318 = arith.subi %316, %317 : i32
      memref.store %318, %alloc_91[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_91[%arg95] : memref<2xi32, strided<[1]>>
      %317 = arith.muli %316, %316 : i32
      memref.store %317, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    %alloc_92 = memref.alloc() {alignment = 64 : i64} : memref<1xi64, strided<[1]>>
    %193 = memref.load %alloc_62[%c0] : memref<1xi64, strided<[1]>>
    memref.store %193, %alloc_92[%c0] : memref<1xi64, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %alloc_92[%c0] : memref<1xi64, strided<[1]>>
      %318 = arith.extsi %316 : i32 to i64
      %319 = arith.addi %318, %317 : i64
      memref.store %319, %alloc_92[%c0] : memref<1xi64, strided<[1]>>
    }
    %194 = memref.load %alloc_92[%c0] : memref<1xi64, strided<[1]>>
    %195 = arith.trunci %194 : i64 to i32
    memref.store %195, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %196 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %197 = memref.load %arg56[] : memref<i32>
    %198 = arith.shrsi %196, %197 : i32
    memref.store %198, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %199 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %200 = memref.load %arg63[] : memref<i32>
    %201 = arith.cmpi sgt, %199, %200 : i32
    %202 = arith.select %201, %199, %200 : i32
    memref.store %202, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %203 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %204 = memref.load %arg64[] : memref<i32>
    %205 = arith.cmpi slt, %203, %204 : i32
    %206 = arith.select %205, %203, %204 : i32
    memref.store %206, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %207 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %208 = memref.load %arg57[] : memref<i32>
    %209 = arith.shrsi %207, %208 : i32
    memref.store %209, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %210 = memref.load %arg59[] : memref<i32>
    %211 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %212 = arith.subi %210, %211 : i32
    memref.store %212, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %213 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %214 = memref.load %arg60[] : memref<i32>
    %215 = arith.cmpi sgt, %213, %214 : i32
    %216 = arith.select %215, %213, %214 : i32
    memref.store %216, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_91[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
      %318 = arith.muli %316, %317 : i32
      memref.store %318, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %arg58[] : memref<i32>
      %318 = arith.shrsi %316, %317 : i32
      memref.store %318, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %arg54[%arg95] : memref<2xi32>
      %318 = arith.muli %316, %317 : i32
      memref.store %318, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %arg58[] : memref<i32>
      %318 = arith.shrsi %316, %317 : i32
      memref.store %318, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %arg55[%arg95] : memref<2xi32>
      %318 = arith.addi %316, %317 : i32
      memref.store %318, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %arg61[] : memref<i32>
      %318 = arith.cmpi sgt, %316, %317 : i32
      %319 = arith.select %318, %316, %317 : i32
      memref.store %319, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %arg62[] : memref<i32>
      %318 = arith.cmpi slt, %316, %317 : i32
      %319 = arith.select %318, %316, %317 : i32
      memref.store %319, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = arith.sitofp %316 : i32 to f32
      memref.store %317, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_24 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_35 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.extsi %316 : i8 to i32
      %318 = arith.subi %317, %c-128_i32 : i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.mulf %319, %cst_24 : f32
      memref.store %320, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = memref.load %alloc_53[] : memref<f32>
      %318 = arith.mulf %316, %317 : f32
      memref.store %318, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_23 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_35 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      scf.for %arg96 = %c0 to %c2 step %c1 {
        %316 = arith.muli %arg96, %c2 overflow<nsw> : index
        %317 = arith.addi %316, %arg95 : index
        %318 = memref.load %alloc_43[%317] : memref<4xi8, strided<[1]>>
        %319 = arith.muli %arg95, %c2 overflow<nsw> : index
        %320 = arith.addi %319, %arg96 : index
        memref.store %318, %alloc[%320] : memref<4xi8, strided<[1]>>
      }
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      scf.for %arg96 = %c0 to %c2 step %c1 {
        %316 = arith.muli %arg95, %c2 overflow<nsw> : index
        %317 = arith.addi %316, %arg96 : index
        %318 = memref.load %alloc[%317] : memref<4xi8, strided<[1]>>
        memref.store %318, %alloc_67[%317] : memref<4xi8, strided<[1]>>
      }
    }
    %alloc_93 = memref.alloc() {alignment = 64 : i64} : memref<2xi32, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_68[%arg95] : memref<2xi32, strided<[1]>>
      memref.store %316, %alloc_93[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      scf.for %arg96 = %c0 to %c2 step %c1 {
        %316 = memref.load %alloc_56[%arg96] : memref<2xi8, strided<[1]>>
        %317 = arith.muli %arg96, %c2 overflow<nsw> : index
        %318 = arith.addi %317, %arg95 : index
        %319 = memref.load %alloc_67[%318] : memref<4xi8, strided<[1]>>
        %320 = memref.load %alloc_93[%arg95] : memref<2xi32, strided<[1]>>
        %321 = arith.extsi %316 : i8 to i32
        %322 = arith.subi %321, %c-128_i32 : i32
        %323 = arith.extsi %319 : i8 to i32
        %324 = arith.muli %322, %323 : i32
        %325 = arith.addi %320, %324 : i32
        memref.store %325, %alloc_93[%arg95] : memref<2xi32, strided<[1]>>
      }
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_93[%arg95] : memref<2xi32, strided<[1]>>
      %317 = arith.sitofp %316 : i32 to f32
      %318 = arith.mulf %317, %cst_1 : f32
      memref.store %318, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_34 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_12 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.extsi %316 : i8 to i32
      %318 = arith.subi %317, %c-125_i32 : i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.mulf %319, %cst_34 : f32
      memref.store %320, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_34 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_12 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_70[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_70[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_70[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_70[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_70[%arg95] : memref<2xi8, strided<[1]>>
    }
    %alloc_94 = memref.alloc() {alignment = 64 : i64} : memref<2xf32, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_70[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.extsi %316 : i8 to i32
      %318 = arith.subi %317, %c-125_i32 : i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.mulf %319, %cst_34 : f32
      memref.store %320, %alloc_94[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_94[%arg95] : memref<2xf32, strided<[1]>>
      memref.store %316, %alloc_71[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_71[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_34 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_12 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_70[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_70[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_70[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_70[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_70[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_70[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.extsi %316 : i8 to i32
      %318 = arith.subi %317, %c-125_i32 : i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.mulf %319, %cst_34 : f32
      memref.store %320, %alloc_71[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %6[%c0] : memref<1xf32>
      %317 = memref.load %alloc_71[%arg95] : memref<2xf32, strided<[1]>>
      %318 = memref.load %alloc_73[%arg95] : memref<2xf32, strided<[1]>>
      %319 = arith.mulf %316, %317 : f32
      %320 = arith.addf %318, %319 : f32
      memref.store %320, %alloc_73[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_73[%arg95] : memref<2xf32, strided<[1]>>
      memref.store %316, %alloc_71[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_71[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_34 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_12 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      scf.for %arg96 = %c0 to %c2 step %c1 {
        %316 = arith.muli %arg96, %c2 overflow<nsw> : index
        %317 = arith.addi %316, %arg95 : index
        %318 = memref.load %alloc_44[%317] : memref<4xi8, strided<[1]>>
        %319 = arith.muli %arg95, %c2 overflow<nsw> : index
        %320 = arith.addi %319, %arg96 : index
        memref.store %318, %alloc[%320] : memref<4xi8, strided<[1]>>
      }
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      scf.for %arg96 = %c0 to %c2 step %c1 {
        %316 = arith.muli %arg95, %c2 overflow<nsw> : index
        %317 = arith.addi %316, %arg96 : index
        %318 = memref.load %alloc[%317] : memref<4xi8, strided<[1]>>
        memref.store %318, %alloc_67[%317] : memref<4xi8, strided<[1]>>
      }
    }
    %alloc_95 = memref.alloc() {alignment = 64 : i64} : memref<2xi32, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_68[%arg95] : memref<2xi32, strided<[1]>>
      memref.store %316, %alloc_95[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      scf.for %arg96 = %c0 to %c2 step %c1 {
        %316 = memref.load %alloc_56[%arg96] : memref<2xi8, strided<[1]>>
        %317 = arith.muli %arg96, %c2 overflow<nsw> : index
        %318 = arith.addi %317, %arg95 : index
        %319 = memref.load %alloc_67[%318] : memref<4xi8, strided<[1]>>
        %320 = memref.load %alloc_95[%arg95] : memref<2xi32, strided<[1]>>
        %321 = arith.extsi %316 : i8 to i32
        %322 = arith.subi %321, %c-125_i32 : i32
        %323 = arith.extsi %319 : i8 to i32
        %324 = arith.muli %322, %323 : i32
        %325 = arith.addi %320, %324 : i32
        memref.store %325, %alloc_95[%arg95] : memref<2xi32, strided<[1]>>
      }
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_95[%arg95] : memref<2xi32, strided<[1]>>
      %317 = arith.sitofp %316 : i32 to f32
      %318 = arith.mulf %317, %cst_11 : f32
      memref.store %318, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = memref.load %2[%arg95] : memref<2xf32>
      %318 = arith.addf %316, %317 : f32
      memref.store %318, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_34 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_35 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.extsi %316 : i8 to i32
      %318 = arith.subi %317, %c-128_i32 : i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.mulf %319, %cst_34 : f32
      memref.store %320, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_34 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_35 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.extsi %316 : i8 to i32
      %318 = arith.subi %317, %c-128_i32 : i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.mulf %319, %cst_34 : f32
      memref.store %320, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = memref.load %alloc_89[%arg95] : memref<2xf32, strided<[1]>>
      %318 = arith.addf %316, %317 : f32
      memref.store %318, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_34 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_14 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    %alloc_96 = memref.alloc() {alignment = 64 : i64} : memref<2xf32, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.extsi %316 : i8 to i32
      %318 = arith.subi %317, %c75_i32 : i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.mulf %319, %cst_34 : f32
      memref.store %320, %alloc_96[%arg95] : memref<2xf32, strided<[1]>>
    }
    %217 = memref.load %arg25[] : memref<i8>
    %218 = arith.cmpi slt, %217, %c-128_i8 : i8
    %219 = arith.select %218, %c-128_i8, %217 : i8
    %220 = arith.cmpi sge, %219, %c127_i8 : i8
    %221 = arith.select %220, %c127_i8, %219 : i8
    memref.store %221, %alloc_48[] : memref<i8>
    %222 = memref.load %alloc_48[] : memref<i8>
    %223 = arith.extsi %222 : i8 to i32
    %224 = arith.subi %223, %c-128_i32 : i32
    %225 = arith.sitofp %224 : i32 to f32
    %226 = arith.mulf %225, %cst_26 : f32
    memref.store %226, %alloc_49[] : memref<f32>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_96[%arg95] : memref<2xf32, strided<[1]>>
      %317 = memref.load %alloc_49[] : memref<f32>
      %318 = arith.mulf %316, %317 : f32
      memref.store %318, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_10 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_36 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.extsi %316 : i8 to i32
      %318 = arith.subi %317, %c127_i32 : i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.mulf %319, %cst_10 : f32
      memref.store %320, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.fptosi %316 : f32 to i32
      %318 = arith.sitofp %317 : i32 to f32
      %319 = arith.subf %316, %318 : f32
      %320 = arith.andi %317, %c1_i32 : i32
      %321 = arith.cmpi ne, %320, %c0_i32 : i32
      %322 = arith.cmpf ogt, %319, %cst_5 : f32
      %323 = arith.cmpf oeq, %319, %cst_5 : f32
      %324 = arith.andi %323, %321 : i1
      %325 = arith.ori %322, %324 : i1
      %326 = arith.cmpf olt, %319, %cst_4 : f32
      %327 = arith.cmpf oeq, %319, %cst_4 : f32
      %328 = arith.andi %327, %321 : i1
      %329 = arith.ori %326, %328 : i1
      %330 = arith.extui %325 : i1 to i32
      %331 = arith.select %329, %c-1_i32, %c0_i32 : i32
      %332 = arith.addi %317, %330 : i32
      %333 = arith.addi %332, %331 : i32
      %334 = arith.sitofp %333 : i32 to f32
      memref.store %334, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = memref.load %arg73[] : memref<i32>
      %318 = memref.load %arg74[] : memref<i32>
      %319 = arith.sitofp %317 : i32 to f32
      %320 = arith.cmpf ult, %316, %319 : f32
      %321 = arith.select %320, %319, %316 : f32
      %322 = arith.sitofp %318 : i32 to f32
      %323 = arith.cmpf ugt, %321, %322 : f32
      %324 = arith.select %323, %322, %321 : f32
      memref.store %324, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.fptosi %316 : f32 to i32
      memref.store %317, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    %alloc_97 = memref.alloc() {alignment = 64 : i64} : memref<1xi64, strided<[1]>>
    %227 = memref.load %alloc_62[%c0] : memref<1xi64, strided<[1]>>
    memref.store %227, %alloc_97[%c0] : memref<1xi64, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %alloc_97[%c0] : memref<1xi64, strided<[1]>>
      %318 = arith.extsi %316 : i32 to i64
      %319 = arith.addi %318, %317 : i64
      memref.store %319, %alloc_97[%c0] : memref<1xi64, strided<[1]>>
    }
    %228 = memref.load %alloc_97[%c0] : memref<1xi64, strided<[1]>>
    %229 = arith.trunci %228 : i64 to i32
    memref.store %229, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %230 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %231 = memref.load %arg68[] : memref<i32>
    %232 = arith.shrsi %230, %231 : i32
    memref.store %232, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %alloc_98 = memref.alloc() {alignment = 64 : i64} : memref<2xi32, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
      %318 = arith.subi %316, %317 : i32
      memref.store %318, %alloc_98[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_98[%arg95] : memref<2xi32, strided<[1]>>
      %317 = arith.muli %316, %316 : i32
      memref.store %317, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    %alloc_99 = memref.alloc() {alignment = 64 : i64} : memref<1xi64, strided<[1]>>
    %233 = memref.load %alloc_62[%c0] : memref<1xi64, strided<[1]>>
    memref.store %233, %alloc_99[%c0] : memref<1xi64, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %alloc_99[%c0] : memref<1xi64, strided<[1]>>
      %318 = arith.extsi %316 : i32 to i64
      %319 = arith.addi %318, %317 : i64
      memref.store %319, %alloc_99[%c0] : memref<1xi64, strided<[1]>>
    }
    %234 = memref.load %alloc_99[%c0] : memref<1xi64, strided<[1]>>
    %235 = arith.trunci %234 : i64 to i32
    memref.store %235, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %236 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %237 = memref.load %arg68[] : memref<i32>
    %238 = arith.shrsi %236, %237 : i32
    memref.store %238, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %239 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %240 = memref.load %arg75[] : memref<i32>
    %241 = arith.cmpi sgt, %239, %240 : i32
    %242 = arith.select %241, %239, %240 : i32
    memref.store %242, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %243 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %244 = memref.load %arg76[] : memref<i32>
    %245 = arith.cmpi slt, %243, %244 : i32
    %246 = arith.select %245, %243, %244 : i32
    memref.store %246, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %247 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %248 = memref.load %arg69[] : memref<i32>
    %249 = arith.shrsi %247, %248 : i32
    memref.store %249, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %250 = memref.load %arg71[] : memref<i32>
    %251 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %252 = arith.subi %250, %251 : i32
    memref.store %252, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %253 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %254 = memref.load %arg72[] : memref<i32>
    %255 = arith.cmpi sgt, %253, %254 : i32
    %256 = arith.select %255, %253, %254 : i32
    memref.store %256, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_98[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
      %318 = arith.muli %316, %317 : i32
      memref.store %318, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %arg70[] : memref<i32>
      %318 = arith.shrsi %316, %317 : i32
      memref.store %318, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %arg66[%arg95] : memref<2xi32>
      %318 = arith.muli %316, %317 : i32
      memref.store %318, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %arg70[] : memref<i32>
      %318 = arith.shrsi %316, %317 : i32
      memref.store %318, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %arg67[%arg95] : memref<2xi32>
      %318 = arith.addi %316, %317 : i32
      memref.store %318, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %arg73[] : memref<i32>
      %318 = arith.cmpi sgt, %316, %317 : i32
      %319 = arith.select %318, %316, %317 : i32
      memref.store %319, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %arg74[] : memref<i32>
      %318 = arith.cmpi slt, %316, %317 : i32
      %319 = arith.select %318, %316, %317 : i32
      memref.store %319, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = arith.sitofp %316 : i32 to f32
      memref.store %317, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_24 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_35 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.extsi %316 : i8 to i32
      %318 = arith.subi %317, %c-128_i32 : i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.mulf %319, %cst_24 : f32
      memref.store %320, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = memref.load %alloc_54[] : memref<f32>
      %318 = arith.mulf %316, %317 : f32
      memref.store %318, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_23 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_35 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      scf.for %arg96 = %c0 to %c8 step %c1 {
        %316 = arith.muli %arg96, %c2 overflow<nsw> : index
        %317 = arith.addi %316, %arg95 : index
        %318 = memref.load %alloc_45[%317] : memref<16xi8, strided<[1]>>
        %319 = arith.muli %arg95, %c8 overflow<nsw> : index
        %320 = arith.addi %319, %arg96 : index
        memref.store %318, %alloc_41[%320] : memref<16xi8, strided<[1]>>
      }
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      scf.for %arg96 = %c0 to %c8 step %c1 {
        %316 = arith.muli %arg95, %c8 overflow<nsw> : index
        %317 = arith.addi %316, %arg96 : index
        %318 = memref.load %alloc_41[%317] : memref<16xi8, strided<[1]>>
        memref.store %318, %alloc_80[%317] : memref<16xi8, strided<[1]>>
      }
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      scf.for %arg96 = %c0 to %c2 step %c1 {
        %316 = memref.load %alloc_56[%arg96] : memref<2xi8, strided<[1]>>
        %317 = arith.muli %arg96, %c8 overflow<nsw> : index
        %318 = arith.addi %317, %arg95 : index
        %319 = memref.load %alloc_80[%318] : memref<16xi8, strided<[1]>>
        %320 = memref.load %alloc_81[%arg95] : memref<8xi32, strided<[1]>>
        %321 = arith.extsi %316 : i8 to i32
        %322 = arith.subi %321, %c-128_i32 : i32
        %323 = arith.extsi %319 : i8 to i32
        %324 = arith.muli %322, %323 : i32
        %325 = arith.addi %320, %324 : i32
        memref.store %325, %alloc_81[%arg95] : memref<8xi32, strided<[1]>>
      }
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_81[%arg95] : memref<8xi32, strided<[1]>>
      %317 = arith.sitofp %316 : i32 to f32
      %318 = arith.mulf %317, %cst_0 : f32
      memref.store %318, %alloc_83[%arg95] : memref<8xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_83[%arg95] : memref<8xf32, strided<[1]>>
      %317 = memref.load %1[%arg95] : memref<8xf32>
      %318 = arith.addf %316, %317 : f32
      memref.store %318, %alloc_83[%arg95] : memref<8xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_83[%arg95] : memref<8xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_34 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_9 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
    }
    %alloc_100 = memref.alloc() {alignment = 64 : i64} : memref<8xf32, strided<[1]>>
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
      %317 = arith.extsi %316 : i8 to i32
      %318 = arith.subi %317, %c-118_i32 : i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.mulf %319, %cst_34 : f32
      memref.store %320, %alloc_100[%arg95] : memref<8xf32, strided<[1]>>
    }
    %257 = memref.load %arg26[] : memref<i8>
    %258 = arith.cmpi slt, %257, %c-128_i8 : i8
    %259 = arith.select %258, %c-128_i8, %257 : i8
    %260 = arith.cmpi sge, %259, %c127_i8 : i8
    %261 = arith.select %260, %c127_i8, %259 : i8
    memref.store %261, %alloc_48[] : memref<i8>
    %262 = memref.load %alloc_48[] : memref<i8>
    %263 = arith.extsi %262 : i8 to i32
    %264 = arith.subi %263, %c-128_i32 : i32
    %265 = arith.sitofp %264 : i32 to f32
    %266 = arith.mulf %265, %cst_19 : f32
    memref.store %266, %alloc_49[] : memref<f32>
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_100[%arg95] : memref<8xf32, strided<[1]>>
      %317 = memref.load %alloc_49[] : memref<f32>
      %318 = arith.mulf %316, %317 : f32
      memref.store %318, %alloc_83[%arg95] : memref<8xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_83[%arg95] : memref<8xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_34 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_18 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
    }
    %alloc_101 = memref.alloc() {alignment = 64 : i64} : memref<8xf32, strided<[1]>>
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
      %317 = arith.extsi %316 : i8 to i32
      %318 = arith.subi %317, %c-123_i32 : i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.mulf %319, %cst_34 : f32
      memref.store %320, %alloc_101[%arg95] : memref<8xf32, strided<[1]>>
    }
    %267 = memref.load %arg27[] : memref<i8>
    %268 = arith.cmpi slt, %267, %c-128_i8 : i8
    %269 = arith.select %268, %c-128_i8, %267 : i8
    %270 = arith.cmpi sge, %269, %c127_i8 : i8
    %271 = arith.select %270, %c127_i8, %269 : i8
    memref.store %271, %alloc_48[] : memref<i8>
    %272 = memref.load %alloc_48[] : memref<i8>
    %273 = arith.extsi %272 : i8 to i32
    %274 = arith.subi %273, %c-128_i32 : i32
    %275 = arith.sitofp %274 : i32 to f32
    %276 = arith.mulf %275, %cst_17 : f32
    memref.store %276, %alloc_49[] : memref<f32>
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_100[%arg95] : memref<8xf32, strided<[1]>>
      %317 = memref.load %alloc_49[] : memref<f32>
      %318 = arith.mulf %316, %317 : f32
      memref.store %318, %alloc_83[%arg95] : memref<8xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_83[%arg95] : memref<8xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_34 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_16 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
      %317 = arith.extsi %316 : i8 to i32
      %318 = arith.subi %317, %c-124_i32 : i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.mulf %319, %cst_34 : f32
      memref.store %320, %alloc_83[%arg95] : memref<8xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_83[%arg95] : memref<8xf32, strided<[1]>>
      %317 = memref.load %alloc_100[%arg95] : memref<8xf32, strided<[1]>>
      %318 = arith.mulf %316, %317 : f32
      memref.store %318, %alloc_83[%arg95] : memref<8xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_83[%arg95] : memref<8xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_34 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_35 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
      %317 = arith.extsi %316 : i8 to i32
      %318 = arith.subi %317, %c-128_i32 : i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.mulf %319, %cst_34 : f32
      memref.store %320, %alloc_83[%arg95] : memref<8xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_101[%arg95] : memref<8xf32, strided<[1]>>
      %317 = memref.load %alloc_83[%arg95] : memref<8xf32, strided<[1]>>
      %318 = arith.addf %316, %317 : f32
      memref.store %318, %alloc_83[%arg95] : memref<8xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_83[%arg95] : memref<8xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_34 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_18 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      %316 = memref.load %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_84[%arg95] : memref<8xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      scf.for %arg96 = %c0 to %c2 step %c1 {
        %316 = arith.muli %arg96, %c8 overflow<nsw> : index
        %317 = arith.addi %316, %arg95 : index
        %318 = memref.load %alloc_46[%317] : memref<16xi8, strided<[1]>>
        %319 = arith.muli %arg95, %c2 overflow<nsw> : index
        %320 = arith.addi %319, %arg96 : index
        memref.store %318, %alloc_40[%320] : memref<16xi8, strided<[1]>>
      }
    }
    scf.for %arg95 = %c0 to %c8 step %c1 {
      scf.for %arg96 = %c0 to %c2 step %c1 {
        %316 = arith.muli %arg95, %c2 overflow<nsw> : index
        %317 = arith.addi %316, %arg96 : index
        %318 = memref.load %alloc_40[%317] : memref<16xi8, strided<[1]>>
        memref.store %318, %alloc_87[%317] : memref<16xi8, strided<[1]>>
      }
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      scf.for %arg96 = %c0 to %c8 step %c1 {
        %316 = memref.load %alloc_84[%arg96] : memref<8xi8, strided<[1]>>
        %317 = arith.muli %arg96, %c2 overflow<nsw> : index
        %318 = arith.addi %317, %arg95 : index
        %319 = memref.load %alloc_87[%318] : memref<16xi8, strided<[1]>>
        %320 = memref.load %alloc_68[%arg95] : memref<2xi32, strided<[1]>>
        %321 = arith.extsi %316 : i8 to i32
        %322 = arith.subi %321, %c-123_i32 : i32
        %323 = arith.extsi %319 : i8 to i32
        %324 = arith.muli %322, %323 : i32
        %325 = arith.addi %320, %324 : i32
        memref.store %325, %alloc_68[%arg95] : memref<2xi32, strided<[1]>>
      }
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_68[%arg95] : memref<2xi32, strided<[1]>>
      %317 = arith.sitofp %316 : i32 to f32
      %318 = arith.mulf %317, %cst_8 : f32
      memref.store %318, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = memref.load %0[%arg95] : memref<2xf32>
      %318 = arith.addf %316, %317 : f32
      memref.store %318, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_34 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_35 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.extsi %316 : i8 to i32
      %318 = arith.subi %317, %c-128_i32 : i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.mulf %319, %cst_34 : f32
      memref.store %320, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_34 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_35 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.extsi %316 : i8 to i32
      %318 = arith.subi %317, %c-128_i32 : i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.mulf %319, %cst_34 : f32
      memref.store %320, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_96[%arg95] : memref<2xf32, strided<[1]>>
      %317 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %318 = arith.addf %316, %317 : f32
      memref.store %318, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_34 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_14 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.extsi %316 : i8 to i32
      %318 = arith.subi %317, %c75_i32 : i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.mulf %319, %cst_34 : f32
      memref.store %320, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    %277 = memref.load %arg28[] : memref<i8>
    %278 = arith.cmpi slt, %277, %c-128_i8 : i8
    %279 = arith.select %278, %c-128_i8, %277 : i8
    %280 = arith.cmpi sge, %279, %c127_i8 : i8
    %281 = arith.select %280, %c127_i8, %279 : i8
    memref.store %281, %alloc_48[] : memref<i8>
    %282 = memref.load %alloc_48[] : memref<i8>
    %283 = arith.extsi %282 : i8 to i32
    %284 = arith.subi %283, %c-128_i32 : i32
    %285 = arith.sitofp %284 : i32 to f32
    %286 = arith.mulf %285, %cst_26 : f32
    memref.store %286, %alloc_49[] : memref<f32>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = memref.load %alloc_49[] : memref<f32>
      %318 = arith.mulf %316, %317 : f32
      memref.store %318, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_7 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_36 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.extsi %316 : i8 to i32
      %318 = arith.subi %317, %c127_i32 : i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.mulf %319, %cst_7 : f32
      memref.store %320, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.fptosi %316 : f32 to i32
      %318 = arith.sitofp %317 : i32 to f32
      %319 = arith.subf %316, %318 : f32
      %320 = arith.andi %317, %c1_i32 : i32
      %321 = arith.cmpi ne, %320, %c0_i32 : i32
      %322 = arith.cmpf ogt, %319, %cst_5 : f32
      %323 = arith.cmpf oeq, %319, %cst_5 : f32
      %324 = arith.andi %323, %321 : i1
      %325 = arith.ori %322, %324 : i1
      %326 = arith.cmpf olt, %319, %cst_4 : f32
      %327 = arith.cmpf oeq, %319, %cst_4 : f32
      %328 = arith.andi %327, %321 : i1
      %329 = arith.ori %326, %328 : i1
      %330 = arith.extui %325 : i1 to i32
      %331 = arith.select %329, %c-1_i32, %c0_i32 : i32
      %332 = arith.addi %317, %330 : i32
      %333 = arith.addi %332, %331 : i32
      %334 = arith.sitofp %333 : i32 to f32
      memref.store %334, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = memref.load %arg89[] : memref<i32>
      %318 = memref.load %arg90[] : memref<i32>
      %319 = arith.sitofp %317 : i32 to f32
      %320 = arith.cmpf ult, %316, %319 : f32
      %321 = arith.select %320, %319, %316 : f32
      %322 = arith.sitofp %318 : i32 to f32
      %323 = arith.cmpf ugt, %321, %322 : f32
      %324 = arith.select %323, %322, %321 : f32
      memref.store %324, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.fptosi %316 : f32 to i32
      memref.store %317, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    %alloc_102 = memref.alloc() {alignment = 64 : i64} : memref<1xi64, strided<[1]>>
    %287 = memref.load %alloc_62[%c0] : memref<1xi64, strided<[1]>>
    memref.store %287, %alloc_102[%c0] : memref<1xi64, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %alloc_102[%c0] : memref<1xi64, strided<[1]>>
      %318 = arith.extsi %316 : i32 to i64
      %319 = arith.addi %318, %317 : i64
      memref.store %319, %alloc_102[%c0] : memref<1xi64, strided<[1]>>
    }
    %288 = memref.load %alloc_102[%c0] : memref<1xi64, strided<[1]>>
    %289 = arith.trunci %288 : i64 to i32
    memref.store %289, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %290 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %291 = memref.load %arg84[] : memref<i32>
    %292 = arith.shrsi %290, %291 : i32
    memref.store %292, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %alloc_103 = memref.alloc() {alignment = 64 : i64} : memref<2xi32, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
      %318 = arith.subi %316, %317 : i32
      memref.store %318, %alloc_103[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_103[%arg95] : memref<2xi32, strided<[1]>>
      %317 = arith.muli %316, %316 : i32
      memref.store %317, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %alloc_62[%c0] : memref<1xi64, strided<[1]>>
      %318 = arith.extsi %316 : i32 to i64
      %319 = arith.addi %318, %317 : i64
      memref.store %319, %alloc_62[%c0] : memref<1xi64, strided<[1]>>
    }
    %293 = memref.load %alloc_62[%c0] : memref<1xi64, strided<[1]>>
    %294 = arith.trunci %293 : i64 to i32
    memref.store %294, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %295 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %296 = memref.load %arg84[] : memref<i32>
    %297 = arith.shrsi %295, %296 : i32
    memref.store %297, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %298 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %299 = memref.load %arg91[] : memref<i32>
    %300 = arith.cmpi sgt, %298, %299 : i32
    %301 = arith.select %300, %298, %299 : i32
    memref.store %301, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %302 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %303 = memref.load %arg92[] : memref<i32>
    %304 = arith.cmpi slt, %302, %303 : i32
    %305 = arith.select %304, %302, %303 : i32
    memref.store %305, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %306 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %307 = memref.load %arg85[] : memref<i32>
    %308 = arith.shrsi %306, %307 : i32
    memref.store %308, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %309 = memref.load %arg87[] : memref<i32>
    %310 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %311 = arith.subi %309, %310 : i32
    memref.store %311, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %312 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    %313 = memref.load %arg88[] : memref<i32>
    %314 = arith.cmpi sgt, %312, %313 : i32
    %315 = arith.select %314, %312, %313 : i32
    memref.store %315, %alloc_64[%c0] : memref<1xi32, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_103[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %alloc_64[%c0] : memref<1xi32, strided<[1]>>
      %318 = arith.muli %316, %317 : i32
      memref.store %318, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %arg86[] : memref<i32>
      %318 = arith.shrsi %316, %317 : i32
      memref.store %318, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %arg82[%arg95] : memref<2xi32>
      %318 = arith.muli %316, %317 : i32
      memref.store %318, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %arg86[] : memref<i32>
      %318 = arith.shrsi %316, %317 : i32
      memref.store %318, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %arg83[%arg95] : memref<2xi32>
      %318 = arith.addi %316, %317 : i32
      memref.store %318, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %arg89[] : memref<i32>
      %318 = arith.cmpi sgt, %316, %317 : i32
      %319 = arith.select %318, %316, %317 : i32
      memref.store %319, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = memref.load %arg90[] : memref<i32>
      %318 = arith.cmpi slt, %316, %317 : i32
      %319 = arith.select %318, %316, %317 : i32
      memref.store %319, %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_61[%arg95] : memref<2xi32, strided<[1]>>
      %317 = arith.sitofp %316 : i32 to f32
      memref.store %317, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_24 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_35 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.extsi %316 : i8 to i32
      %318 = arith.subi %317, %c-128_i32 : i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.mulf %319, %cst_24 : f32
      memref.store %320, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = memref.load %alloc_55[] : memref<f32>
      %318 = arith.mulf %316, %317 : f32
      memref.store %318, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_23 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_35 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.extsi %316 : i8 to i32
      %318 = arith.subi %317, %c-128_i32 : i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.mulf %319, %cst_23 : f32
      memref.store %320, %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_57[%arg95] : memref<2xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_23 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_35 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c2 step %c1 {
      %316 = memref.load %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_56[%arg95] : memref<2xi8, strided<[1]>>
    }
    %alloc_104 = memref.alloc() {alignment = 64 : i64} : memref<64xi8, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      scf.for %arg96 = %c0 to %c32 step %c1 {
        %316 = arith.muli %arg96, %c2 overflow<nsw> : index
        %317 = arith.addi %316, %arg95 : index
        %318 = memref.load %alloc_47[%317] : memref<64xi8, strided<[1]>>
        %319 = arith.muli %arg95, %c32 overflow<nsw> : index
        %320 = arith.addi %319, %arg96 : index
        memref.store %318, %alloc_104[%320] : memref<64xi8, strided<[1]>>
      }
    }
    %alloc_105 = memref.alloc() {alignment = 64 : i64} : memref<64xi8, strided<[1]>>
    scf.for %arg95 = %c0 to %c2 step %c1 {
      scf.for %arg96 = %c0 to %c32 step %c1 {
        %316 = arith.muli %arg95, %c32 overflow<nsw> : index
        %317 = arith.addi %316, %arg96 : index
        %318 = memref.load %alloc_104[%317] : memref<64xi8, strided<[1]>>
        memref.store %318, %alloc_105[%317] : memref<64xi8, strided<[1]>>
      }
    }
    %alloc_106 = memref.alloc() {alignment = 64 : i64} : memref<32xi32, strided<[1]>>
    scf.for %arg95 = %c0 to %c32 step %c1 {
      memref.store %c0_i32, %alloc_106[%arg95] : memref<32xi32, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c32 step %c1 {
      scf.for %arg96 = %c0 to %c2 step %c1 {
        %316 = memref.load %alloc_56[%arg96] : memref<2xi8, strided<[1]>>
        %317 = arith.muli %arg96, %c32 overflow<nsw> : index
        %318 = arith.addi %317, %arg95 : index
        %319 = memref.load %alloc_105[%318] : memref<64xi8, strided<[1]>>
        %320 = memref.load %alloc_106[%arg95] : memref<32xi32, strided<[1]>>
        %321 = arith.extsi %316 : i8 to i32
        %322 = arith.subi %321, %c-128_i32 : i32
        %323 = arith.extsi %319 : i8 to i32
        %324 = arith.muli %322, %323 : i32
        %325 = arith.addi %320, %324 : i32
        memref.store %325, %alloc_106[%arg95] : memref<32xi32, strided<[1]>>
      }
    }
    %alloc_107 = memref.alloc() {alignment = 64 : i64} : memref<32xf32, strided<[1]>>
    scf.for %arg95 = %c0 to %c32 step %c1 {
      %316 = memref.load %alloc_106[%arg95] : memref<32xi32, strided<[1]>>
      %317 = arith.sitofp %316 : i32 to f32
      %318 = arith.mulf %317, %cst : f32
      memref.store %318, %alloc_107[%arg95] : memref<32xf32, strided<[1]>>
    }
    %alloc_108 = memref.alloc() {alignment = 64 : i64} : memref<32xi8, strided<[1]>>
    scf.for %arg95 = %c0 to %c32 step %c1 {
      %316 = memref.load %alloc_107[%arg95] : memref<32xf32, strided<[1]>>
      %317 = arith.divf %316, %cst_34 : f32
      %318 = arith.fptosi %317 : f32 to i32
      %319 = arith.sitofp %318 : i32 to f32
      %320 = arith.subf %317, %319 : f32
      %321 = arith.andi %318, %c1_i32 : i32
      %322 = arith.cmpi ne, %321, %c0_i32 : i32
      %323 = arith.cmpf ogt, %320, %cst_5 : f32
      %324 = arith.cmpf oeq, %320, %cst_5 : f32
      %325 = arith.andi %324, %322 : i1
      %326 = arith.ori %323, %325 : i1
      %327 = arith.cmpf olt, %320, %cst_4 : f32
      %328 = arith.cmpf oeq, %320, %cst_4 : f32
      %329 = arith.andi %328, %322 : i1
      %330 = arith.ori %327, %329 : i1
      %331 = arith.extui %326 : i1 to i32
      %332 = arith.select %330, %c-1_i32, %c0_i32 : i32
      %333 = arith.addi %318, %331 : i32
      %334 = arith.addi %333, %332 : i32
      %335 = arith.sitofp %334 : i32 to f32
      %336 = arith.addf %335, %cst_6 : f32
      %337 = arith.cmpf ugt, %336, %cst_35 : f32
      %338 = arith.select %337, %336, %cst_35 : f32
      %339 = arith.cmpf ult, %338, %cst_36 : f32
      %340 = arith.select %339, %338, %cst_36 : f32
      %341 = arith.fptosi %340 : f32 to i8
      memref.store %341, %alloc_108[%arg95] : memref<32xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c32 step %c1 {
      %316 = memref.load %alloc_108[%arg95] : memref<32xi8, strided<[1]>>
      %317 = arith.cmpi slt, %316, %c-128_i8 : i8
      %318 = arith.select %317, %c-128_i8, %316 : i8
      %319 = arith.cmpi sge, %318, %c127_i8 : i8
      %320 = arith.select %319, %c127_i8, %318 : i8
      memref.store %320, %alloc_108[%arg95] : memref<32xi8, strided<[1]>>
    }
    scf.for %arg95 = %c0 to %c32 step %c1 {
      %316 = memref.load %alloc_108[%arg95] : memref<32xi8, strided<[1]>>
      memref.store %316, %arg94[%arg95] : memref<32xi8>
    }
    return
  }
}
