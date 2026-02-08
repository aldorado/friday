{
  description = "jarvis — AI messaging agent powered by Claude Code";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        python = pkgs.python312;

        pythonEnv = python.withPackages (ps: with ps; [
          fastapi
          httpx
          uvicorn
          python-dotenv
          openai
          numpy
          pandas
          pyarrow
          python-crontab
          elevenlabs
          # uvicorn extras
          websockets
          httptools
          uvloop
        ]);
      in
      {
        packages.default = pkgs.stdenv.mkDerivation {
          pname = "jarvis";
          version = "0.1.0";
          src = ./.;

          buildInputs = [ pythonEnv ];
          nativeBuildInputs = [ pkgs.makeWrapper ];

          installPhase = ''
            mkdir -p $out/lib/jarvis $out/bin
            cp -r jarvis $out/lib/jarvis/
            cp -r scripts $out/lib/jarvis/
            cp -r .claude $out/lib/jarvis/
            cp pyproject.toml $out/lib/jarvis/
            [ -f news.md ] && cp news.md $out/lib/jarvis/ || true

            makeWrapper ${pythonEnv}/bin/python $out/bin/jarvis \
              --add-flags "-m jarvis.main" \
              --chdir "$out/lib/jarvis" \
              --prefix PYTHONPATH : "$out/lib/jarvis"
          '';
        };

        devShells.default = pkgs.mkShell {
          packages = [
            pythonEnv
            pkgs.uv
          ];

          shellHook = ''
            export PYTHONPATH="$PWD:$PYTHONPATH"
          '';
        };

        apps.default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/jarvis";
        };
      });
}
