--[[  CHAT CONNECT auto-launcher for OBS  ------------------------------------

Add this in OBS via  Tools > Scripts > [+]  and select this file.
From then on, starting OBS also starts:

  * CHAT CONNECT   (the Twitch + YouTube chat hub, in the background)
  * CHAT YAPPER    (the Duck TTS, in the background)

and (optionally) stops them again when OBS closes.

Both tools are safe to double-launch: if they are already running, the new
copy just exits. Requires install.bat to have been run once in both folders.
------------------------------------------------------------------------------]]

obs = obslua

local launch_server = true
local launch_yapper = true
local stop_on_exit = true

local IS_WINDOWS = package.config:sub(1, 1) == "\\"

local function server_dir()
    return script_path()                       -- this script lives in CHAT_CONNECT/
end

local function yapper_dir()
    return script_path() .. "../CHAT_YAPPER/"
end

local function winpath(p)
    return (p:gsub("/", "\\"))
end

local function launch_bat(dir, bat)
    if IS_WINDOWS then
        os.execute('start "" /min "' .. winpath(dir .. bat) .. '"')
    else
        -- best effort for macOS / Linux (needs the .venv created by install.sh)
        os.execute('cd "' .. dir .. '" && nohup ./.venv/bin/python main.py ' ..
                   '>/dev/null 2>&1 &')
    end
end

local function launch_tools()
    if launch_server then
        obs.script_log(obs.LOG_INFO, "starting CHAT CONNECT...")
        launch_bat(server_dir(), "autolaunch.bat")
    end
    if launch_yapper then
        obs.script_log(obs.LOG_INFO, "starting CHAT YAPPER (duck TTS)...")
        launch_bat(yapper_dir(), "autolaunch.bat")
    end
end

local function stop_tools()
    -- Stopping CHAT CONNECT is enough: the Duck was launched in follow mode
    -- (CHAT_YAPPER_EXIT_WITH_SERVER=1) and exits by itself when the hub stops.
    if IS_WINDOWS then
        os.execute('start "" /min cmd /c curl -s -m 3 -X POST ' ..
                   'http://127.0.0.1:2428/api/shutdown')
    else
        os.execute('curl -s -m 3 -X POST http://127.0.0.1:2428/api/shutdown ' ..
                   '>/dev/null 2>&1 &')
    end
end

-- ----------------------------------------------------------- OBS scripting API

function script_description()
    return [[<b>CHAT CONNECT auto-launcher</b><br>
Starts CHAT CONNECT (Twitch + YouTube chat hub) and CHAT YAPPER (duck TTS)
in the background whenever OBS starts, so everything works without
remembering to launch anything.<br><br>
Dashboard: <code>http://localhost:2428</code>]]
end

function script_properties()
    local props = obs.obs_properties_create()
    obs.obs_properties_add_bool(props, "launch_server",
        "Start CHAT CONNECT with OBS")
    obs.obs_properties_add_bool(props, "launch_yapper",
        "Start CHAT YAPPER (duck TTS) with OBS")
    obs.obs_properties_add_bool(props, "stop_on_exit",
        "Stop them when OBS closes")
    obs.obs_properties_add_button(props, "restart_now",
        "(Re)start the tools now", function()
            launch_tools()
            return false
        end)
    return props
end

function script_defaults(settings)
    obs.obs_data_set_default_bool(settings, "launch_server", true)
    obs.obs_data_set_default_bool(settings, "launch_yapper", true)
    obs.obs_data_set_default_bool(settings, "stop_on_exit", true)
end

function script_update(settings)
    launch_server = obs.obs_data_get_bool(settings, "launch_server")
    launch_yapper = obs.obs_data_get_bool(settings, "launch_yapper")
    stop_on_exit = obs.obs_data_get_bool(settings, "stop_on_exit")
end

function script_load(settings)
    script_update(settings)
    launch_tools()
end

function script_unload()
    if stop_on_exit then
        stop_tools()
    end
end
