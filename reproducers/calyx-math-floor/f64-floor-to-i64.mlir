module {
  // The five input elements exercise positive/negative fractional values,
  // positive/negative exact integers, and negative zero, respectively.
  // Keeping them in memrefs makes @main a memory-backed Calyx probe.
  func.func @main(%input: memref<5xf64>, %output: memref<5xi64>) {
    %c0 = arith.constant 0 : index
    %c1 = arith.constant 1 : index
    %c2 = arith.constant 2 : index
    %c3 = arith.constant 3 : index
    %c4 = arith.constant 4 : index
    %one = arith.constant 1.000000e+00 : f64

    %positive_fraction = memref.load %input[%c0] : memref<5xf64>
    %positive_ratio = arith.divf %positive_fraction, %one : f64
    %positive_floor = math.floor %positive_ratio : f64
    %positive_result = arith.fptosi %positive_floor : f64 to i64
    memref.store %positive_result, %output[%c0] : memref<5xi64>

    %negative_fraction = memref.load %input[%c1] : memref<5xf64>
    %negative_ratio = arith.divf %negative_fraction, %one : f64
    %negative_floor = math.floor %negative_ratio : f64
    %negative_result = arith.fptosi %negative_floor : f64 to i64
    memref.store %negative_result, %output[%c1] : memref<5xi64>

    %positive_integer = memref.load %input[%c2] : memref<5xf64>
    %positive_integer_ratio = arith.divf %positive_integer, %one : f64
    %positive_integer_floor = math.floor %positive_integer_ratio : f64
    %positive_integer_result = arith.fptosi %positive_integer_floor : f64 to i64
    memref.store %positive_integer_result, %output[%c2] : memref<5xi64>

    %negative_integer = memref.load %input[%c3] : memref<5xf64>
    %negative_integer_ratio = arith.divf %negative_integer, %one : f64
    %negative_integer_floor = math.floor %negative_integer_ratio : f64
    %negative_integer_result = arith.fptosi %negative_integer_floor : f64 to i64
    memref.store %negative_integer_result, %output[%c3] : memref<5xi64>

    %negative_zero = memref.load %input[%c4] : memref<5xf64>
    %negative_zero_ratio = arith.divf %negative_zero, %one : f64
    %negative_zero_floor = math.floor %negative_zero_ratio : f64
    %negative_zero_result = arith.fptosi %negative_zero_floor : f64 to i64
    memref.store %negative_zero_result, %output[%c4] : memref<5xi64>
    return
  }

  func.func @standalone_f64_floor(%input: memref<1xf64>, %output: memref<1xf64>) {
    %c0 = arith.constant 0 : index
    %value = memref.load %input[%c0] : memref<1xf64>
    %rounded = math.floor %value : f64
    memref.store %rounded, %output[%c0] : memref<1xf64>
    return
  }

  func.func @two_use_f64_floor(%input: memref<1xf64>, %output: memref<2xi64>) {
    %c0 = arith.constant 0 : index
    %c1 = arith.constant 1 : index
    %value = memref.load %input[%c0] : memref<1xf64>
    %rounded = math.floor %value : f64
    %first = arith.fptosi %rounded : f64 to i64
    %second = arith.fptosi %rounded : f64 to i64
    memref.store %first, %output[%c0] : memref<2xi64>
    memref.store %second, %output[%c1] : memref<2xi64>
    return
  }

  func.func @f64_floor_to_i32(%input: memref<1xf64>, %output: memref<1xi32>) {
    %c0 = arith.constant 0 : index
    %value = memref.load %input[%c0] : memref<1xf64>
    %rounded = math.floor %value : f64
    %result = arith.fptosi %rounded : f64 to i32
    memref.store %result, %output[%c0] : memref<1xi32>
    return
  }

  // This existing f32 legalization is deliberately outside the new f64/i64
  // fused match; its original fptosi-to-i32 consumer remains present.
  func.func @f32_floor_to_i32(%input: memref<1xf32>, %output: memref<1xi32>) {
    %c0 = arith.constant 0 : index
    %value = memref.load %input[%c0] : memref<1xf32>
    %rounded = math.floor %value : f32
    %result = arith.fptosi %rounded : f32 to i32
    memref.store %result, %output[%c0] : memref<1xi32>
    return
  }

  func.func @f64_ceil_rsqrt(%input: memref<2xf64>, %output: memref<2xf64>) {
    %c0 = arith.constant 0 : index
    %c1 = arith.constant 1 : index
    %ceil_input = memref.load %input[%c0] : memref<2xf64>
    %ceil_result = math.ceil %ceil_input : f64
    memref.store %ceil_result, %output[%c0] : memref<2xf64>
    %rsqrt_input = memref.load %input[%c1] : memref<2xf64>
    %rsqrt_result = math.rsqrt %rsqrt_input : f64
    memref.store %rsqrt_result, %output[%c1] : memref<2xf64>
    return
  }
}
