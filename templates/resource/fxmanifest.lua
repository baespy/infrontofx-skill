fx_version "cerulean"
game "gta5"
lua54 "yes"

ui_page "html/index.html"

shared_scripts {
    "@1nfx_lib/init.lua",
    "@1nfx_core/imports.lua",
    "config/config.lua",
    "config/config.shop.lua",
}

client_scripts {
    "core/cl_main.lua",
}

server_scripts {
    "core/sv_main.lua",
}

files {
    "html/index.html",
    "html/css/style.css",
    "html/js/nui.js",
    "html/js/app.js",
}
