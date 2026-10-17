fx_version "cerulean"
game "gta5"
lua54 "yes"
use_experimental_fxv2_oal "yes"

name "infrontofx_template"
author "infrontofx"
version "1.0.0"

ui_page "html/index.html"

shared_scripts {
    "@ox_lib/init.lua",
    "config/config.lua",
    "config/config.shop.lua",
    "core/sh_config.lua",
}

client_scripts {
    "config/function/config.function.client.lua",
    "core/cl_main.lua",
}

server_scripts {
    "config/function/config.function.server.lua",
    "core/sv_main.lua",
}

files {
    "html/**",
}

dependencies {
    "ox_lib",
    "es_extended",
}
