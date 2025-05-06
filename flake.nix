{
    description = "Development environment for the MeshTree Blender addon";

    inputs = {
        nixpkgs.url = "github:NixOS/nixpkgs/d35f5a8";
        flake-utils.url = "github:numtide/flake-utils";
    };

    outputs = { self, nixpkgs, flake-utils, ... }:
        flake-utils.lib.eachDefaultSystem (system:
            let
                pkgs = import nixpkgs {
                    inherit system;
                    config.allowUnfree = true; 
                };

                blenderCustom = (pkgs.blender.overrideAttrs (old: {
                    makeFlags = [ "-j2" ];
                })).override {
                        cudaSupport = true;
                    };
            in {
                devShells.default = pkgs.mkShell {
                    name = "meshtree-dev-shell";

                    packages = [
                        blenderCustom
                        pkgs.python3
                        pkgs.python3Packages.pip
                        pkgs.python3Packages.setuptools
                        pkgs.python3Packages.virtualenv
                    ];

                    shellHook = ''
            echo "🚀 Velkommen til MeshTree utviklingsmiljø!"
            echo "📦 Blender binary: $(which blender)"

            export BLENDER_USER_SCRIPTS="$PWD/.blender_scripts"
            mkdir -p "$BLENDER_USER_SCRIPTS/addons"

            ADDON_NAME="meshtree"
            ADDON_PATH="$PWD"
            ln -sf "$ADDON_PATH" "$BLENDER_USER_SCRIPTS/addons/$ADDON_NAME"

            echo "🔗 Addon linked: $ADDON_PATH -> $BLENDER_USER_SCRIPTS/addons/$ADDON_NAME"
            echo "✅ Nå kan du starte Blender og enable MeshTree fra Add-ons!"
            '';
                };

                apps.default = flake-utils.lib.mkApp {
                    drv = blenderCustom;
                    name = "blender";
                    program = "${blenderCustom}/bin/blender";
                };
            }
        );
}

