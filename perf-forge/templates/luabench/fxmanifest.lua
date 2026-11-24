fx_version "cerulean"
game "gta5"
lua54 "yes"

shared_scripts {
    "@1nfx_lib/init.lua",
    "@1nfx_core/imports.lua",
    "config/config.lua",
    "core/sh_bench.lua",
}

client_scripts {
    "core/cl_main.lua",
}

server_scripts {
    "core/sv_main.lua",
}
