{ lib, rustPlatform, fetchCrate }:

rustPlatform.buildRustPackage rec {
  pname = "calyx";
  version = "0.7.1";

  src = fetchCrate {
    inherit pname version;
    hash = "sha256-ODKIw3gEsoa0rdqNIF/2BK298pkLKMt4IWj/hKTMYEA=";
  };

  cargoHash = "sha256-zweqVJL0/zbsRcQXE96n0ZTgMxRv0jo10vbOZLmyzMY=";

  CALYX_PRIMITIVES_DIR = "${placeholder "out"}/share/calyx";

  doCheck = false;

  postInstall = ''
    mkdir -p "$out/share/calyx"
    cp -r primitives "$out/share/calyx/"
  '';
}
