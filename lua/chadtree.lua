return function(args)
  local cwd = unpack(args)
  local is_win = vim.api.nvim_call_function("has", {"win32"}) == 1

  local function defer(timeout, callback)
    local timer = vim.loop.new_timer()
    timer:start(
      timeout,
      0,
      function()
        timer:stop()
        timer:close()
        vim.schedule(callback)
      end
    )
    return timer
  end

  local settings = function()
    local go, _settings = pcall(vim.api.nvim_get_var, "chadtree_settings")
    local settings = go and _settings or {}
    return settings
  end

  chad = chad or {}
  local linesep = "\n"
  local POLLING_RATE = 10

  if chad.loaded then
    return
  else
    chad.loaded = true
    local job_id = nil
    local err_exit = false

    chad.on_exit = function(args)
      local code = unpack(args)
      local msg = " | CHADTree EXITED - " .. code
      if not (code == 0 or code == 143) then
        err_exit = true
        vim.api.nvim_err_writeln(msg)
      else
        err_exit = false
      end
      job_id = nil
    end

    chad.on_stdout = function(args)
      local msg = unpack(args)
      vim.api.nvim_out_write(table.concat(msg, linesep))
    end

    chad.on_stderr = function(args)
      local msg = unpack(args)
      vim.api.nvim_err_write(table.concat(msg, linesep))
    end

    local go, _py3 = pcall(vim.api.nvim_get_var, "python3_host_prog")
    local py3 = go and _py3 or (is_win and "python" or "python3")

    local main = function(is_xdg)
      local v_py =
        cwd ..
        (is_win and [[/.vars/runtime/Scripts/python.exe]] or
          "/.vars/runtime/bin/python3")
      local win_proxy = cwd .. [[/win.bat]]
      local xdg_dir = vim.api.nvim_call_function("getenv", {"XDG_DATA_HOME"})

      if is_win then
        if vim.api.nvim_call_function("filereadable", {v_py}) == 1 then
          return {v_py}
        else
          return {win_proxy, py3}
        end
      else
        local v_py_xdg =
          xdg_dir and (xdg_dir .. "/nvim/chadtree/runtime/bin/python3") or v_py
        local v_py = is_xdg and v_py_xdg or v_py
        if vim.api.nvim_call_function("filereadable", {v_py}) == 1 then
          return {v_py}
        else
          return {py3}
        end
      end
    end

    local start = function(deps, ...)
      local is_xdg = settings().xdg
      local args =
        vim.tbl_flatten {
        deps and py3 or main(is_xdg),
        {"-m", "chadtree"},
        {...},
        (is_xdg and {"--xdg"} or {})
      }
      local params = {
        cwd = cwd,
        on_exit = "CHADon_exit",
        on_stdout = "CHADon_stdout",
        on_stderr = "CHADon_stderr"
      }
      local job_id = vim.api.nvim_call_function("jobstart", {args, params})
      return job_id
    end

    chad.CHADdeps = function()
      start(true, "deps")
    end

    vim.api.nvim_command [[command! -nargs=0 CHADdeps lua chad.CHADdeps()]]

    local set_chad_call = function(cmd)
      local t1 = 0
      chad[cmd] = function(...)
        local args = {...}
        if t1 == 0 then
          t1 = vim.loop.now()
        end

        if not job_id then
          local server = vim.api.nvim_call_function("serverstart", {})
          job_id = start(false, "run", "--socket", server)
        end

        if not err_exit and _G[cmd] then
          _G[cmd](args)
          t2 = vim.loop.now()
          if settings().profiling and t1 >= 0 then
            print("Init       " .. (t2 - t1) .. "ms")
          end
          t1 = -1
        else
          defer(
            POLLING_RATE,
            function()
              if err_exit then
                return
              else
                chad[cmd](unpack(args))
              end
            end
          )
        end
      end
    end

    set_chad_call("CHADopen")
    vim.api.nvim_command [[command! -nargs=* CHADopen lua chad.CHADopen(<f-args>)]]

    set_chad_call("CHADhelp")
    vim.api.nvim_command [[command! -nargs=* CHADhelp lua chad.CHADhelp(<f-args>)]]

    chad.lsp_ensure_capacities = function(cfg)
      local capabilities = vim.lsp.protocol.make_client_capabilities()
      capabilities.workspace.workspaceEdit.changeAnnotationSupport = true
      local enhancements = {capacities = capacities}
      vim.tbl_deep_extend("force", cfg, enhancements)
    end
  end
end
