--[[  CHAT CONNECT auto-launcher for OBS  ------------------------------------

Add this in OBS via  Tools > Scripts > [+]  and select this file.
From then on, starting OBS also starts:

  * CHAT CONNECT   (the Twitch + YouTube chat hub)
  * CHAT YAPPER    (the Duck TTS)

completely in the background - no terminal windows - and (optionally) stops
them again when OBS closes.

Both tools are safe to double-launch: if they are already running, the new
copy just exits. Requires install.bat to have been run once in both folders;
if it wasn't, an AUTOLAUNCH_ERROR.txt file appears in the tool's folder.
------------------------------------------------------------------------------]]

obs = obslua

local launch_server = true
local launch_yapper = true
local stop_on_exit = true

local IS_WINDOWS = package.config:sub(1, 1) == "\\"
local SW_HIDE = 0

-- On Windows we launch through the ShellExecute API (via LuaJIT FFI) so
-- nothing opens a console window. Plain `start x.bat` is NOT an option: the
-- `start` command runs batch files with `cmd /K`, which leaves an empty
-- terminal window sitting open forever.
local shell32 = nil
local ffi = nil
if IS_WINDOWS then
    local ok, mod = pcall(require, "ffi")
    if ok then
        ffi = mod
        pcall(function()
            ffi.cdef([[
                void* ShellExecuteA(void* hwnd, const char* op, const char* file,
                                    const char* params, const char* dir, int show);
            ]])
            shell32 = ffi.load("shell32")
        end)
    end
end

local function log(msg)
    obs.script_log(obs.LOG_INFO, msg)
end

local function server_dir()
    return script_path()                       -- this script lives in CHAT_CONNECT/
end

local function yapper_dir()
    return script_path() .. "../CHAT_YAPPER/"
end

local function winpath(p)
    return (p:gsub("/", "\\"))
end

local function exists(p)
    local f = io.open(p, "rb")
    if f then f:close() return true end
    return false
end

-- Run `file params` with `dir` as working directory, with a hidden window.
-- Returns true when ShellExecute reports success.
local function shell_execute_hidden(file, params, dir)
    if not shell32 then return false end
    local ok, res = pcall(function()
        local r = shell32.ShellExecuteA(nil, "open", winpath(file), params,
                                        dir and winpath(dir) or nil, SW_HIDE)
        return tonumber(ffi.cast("intptr_t", r))
    end)
    if ok and res and res > 32 then return true end
    obs.script_log(obs.LOG_WARNING,
        "ShellExecute failed (" .. tostring(res) .. ") for " .. file)
    return false
end

-- Start one tool. Preference order on Windows:
--   1. the tool's own venv pythonw.exe, hidden, via ShellExecute  (no window)
--   2. its autolaunch.bat, hidden, via ShellExecute               (no window)
--   3. its autolaunch.bat through `cmd /c`, minimized             (brief flash)
local function start_tool(dir, name, pythonw_args)
    if IS_WINDOWS then
        local pyw = dir .. ".venv/Scripts/pythonw.exe"
        if exists(pyw) and shell_execute_hidden(pyw, pythonw_args, dir) then
            log(name .. ": started hidden (" .. winpath(pyw) .. ")")
            return
        end
        local bat = dir .. "autolaunch.bat"
        if not exists(bat) then
            obs.script_log(obs.LOG_WARNING, name .. ": " .. bat .. " not found")
            return
        end
        if shell_execute_hidden(bat, nil, dir) then
            log(name .. ": started via autolaunch.bat (hidden)")
            return
        end
        -- Explicit `cmd /c` so the batch cannot linger with an open window
        os.execute('start "" /min cmd /c "' .. winpath(bat) .. '"')
        log(name .. ": started via autolaunch.bat (minimized fallback)")
    else
        -- macOS / Linux best effort (needs the .venv created by install.sh)
        os.execute('cd "' .. dir .. '" && nohup ./.venv/bin/python ' ..
                   pythonw_args .. ' >/dev/null 2>&1 &')
        log(name .. ": started in background")
    end
end

local function launch_tools()
    if launch_server then
        start_tool(server_dir(), "CHAT CONNECT", "main.py --log-file server.log")
    end
    if launch_yapper then
        -- --exit-with-server: the Duck quits by itself once the hub stops,
        -- so closing OBS cleans everything up.
        start_tool(yapper_dir(), "CHAT YAPPER", "main.py --exit-with-server")
    end
end

local function stop_tools()
    -- Stopping CHAT CONNECT is enough: the Duck was launched in follow mode
    -- and exits by itself when the hub goes away.
    local args = "-s -m 3 -X POST http://127.0.0.1:2428/api/shutdown"
    if IS_WINDOWS then
        if not shell_execute_hidden("curl.exe", args, nil) then
            os.execute('start "" /min cmd /c curl ' .. args)
        end
    else
        os.execute("curl " .. args .. " >/dev/null 2>&1 &")
    end
    log("sent shutdown to CHAT CONNECT")
end

-- ----------------------------------------------------------- OBS scripting API

function script_description()
    return [[<b>CHAT CONNECT auto-launcher</b><br>
Starts CHAT CONNECT (Twitch + YouTube chat hub) and CHAT YAPPER (duck TTS)
silently in the background whenever OBS starts - no windows, nothing to
remember.<br><br>
Dashboard: <code>http://localhost:2428</code><br>
If a tool does not start, check the Script Log button here and look for an
<code>AUTOLAUNCH_ERROR.txt</code> file in its folder.]]
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
