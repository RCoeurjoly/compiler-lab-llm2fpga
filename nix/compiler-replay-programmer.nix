{ pkgs }:
pkgs.openfpgaloader.overrideAttrs (old: {
  version = "3ae5e5e-bpi-full-verify";
  src = pkgs.fetchFromGitHub {
    owner = "trabucayre";
    repo = "openFPGALoader";
    rev = "3ae5e5e4a5f055d12f6079616cb1ec1d67bf30f1";
    hash = "sha256-dP7wrBVWM06pg7JeQ6Joi39yiuDrTFOuqCIF+yzdnwk=";
  };
  patches = [
    ../patches/openfpgaloader/0001-defer-bpi-bridge.patch
    ../patches/openfpgaloader/0002-full-bpi-verification.patch
  ];
  # Upstream's LibFTDI1 CMake lookup does not set the variables it consumes;
  # use its existing pkg-config fallback, which supplies ftdi.h's include dir.
  cmakeFlags = (old.cmakeFlags or []) ++ [
    "-DENABLE_LIBGPIOD=OFF"
    "-DCMAKE_DISABLE_FIND_PACKAGE_LibFTDI1=TRUE"
  ];
  postInstall = (old.postInstall or "") + ''
    test -f "$out/share/openFPGALoader/bpiOverJtag_xc7k480tffg1156.bit.gz"
    "$out/bin/openFPGALoader" --help | grep -F 'SPI/BPI'
  '';
})
