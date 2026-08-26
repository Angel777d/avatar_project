# Supervisor — design

One pure-stdlib python script, `supervisor.py`, that keeps the app installed and running.
Replaces the .NET supervisor, which ships until this lands.

## Install

`install.bat` is the only download, and re-running it is the update.

```bat
set "DIR=%LOCALAPPDATA%\avatar"
set "UV_UNMANAGED_INSTALL=%DIR%\uv"
set "UV_PYTHON_INSTALL_DIR=%DIR%\python"
set "UV_PYTHON_INSTALL_BIN=0"
set "UV_CACHE_DIR=%DIR%\cache"

curl -fsSL -o "%DIR%\config.json"   "%BASE%/config.json"
curl -fsSL -o "%DIR%\supervisor.py" "%BASE%/supervisor.py"
powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
"%DIR%\uv\uv.exe" python install 3.13
```

Then `uv python find 3.13`, a desktop shortcut to the `pythonw.exe` beside it running
`supervisor.py`, and start it.

- `pythonw.exe`, so there is no console.
- `uv python find` returns a path without a patch version, so the shortcut survives 3.13.15
  becoming 3.13.16.
- `UV_PYTHON_INSTALL_BIN=0`, or `uv` also writes a launcher into `~/.local/bin`.
- The shortcut is rewritten every install, not only when missing, so an icon or a moved
  interpreter reaches the shortcuts that already exist. `avatar.ico` is fetched beside the
  script; failing to get one costs the icon and nothing else.

## config.json

Read by both the supervisor and the app.

```json
{
	"python": "3.13",
	"port": 8731,
	"packages": [
		"angelovich.core==0.2.1",
		"avatar.api @ https://github.com/…/avatar_api-0.2.2-py3-none-any.whl",
		"avatar.core @ https://github.com/…/avatar_core-0.2.2-py3-none-any.whl",
		"avatar.ui @ https://github.com/…/avatar_ui-0.2.2-py3-none-any.whl",
		"avatar_default @ https://github.com/…/avatar_default-0.2.2-py3-none-any.whl",
		"avatar_manager @ https://github.com/…/avatar_manager-0.2.2-py3-none-any.whl"
	],
	"app": { "module": "avatar_core", "restarts": 3, "window": 60, "backoff": 2 }
}
```

## Packages

Desired set is `config.packages` plus every entry of `plugins.json`.

- `plugins.json` may ship with the install; absent means an empty list. The app writes it, the
  supervisor reads it.
- Validate every `plugins.json` entry before use: `name==version`, or an `https://github.com/…`
  url. No newline, no leading dash. Passed to uv as arguments, never through a requirements file.
- `state.json` holds the desired set from the last successful reconcile. Equal means no work.
- Reconcile installs what is missing, updates what moved, and uninstalls what the recorded set
  had and the desired set does not. **Removals come only from that record** — everything else in
  the venv is a dependency of something being kept.
- Record the new set only after the install succeeds.
- A clean reconcile is `uv venv --clear` then one install of the desired set.

## Exchange

`asyncio.start_server` in the supervisor, `asyncio.open_connection` in the app. `127.0.0.1` on
`config.port`. Newline-delimited JSON. No token.

Binding the port is the single-instance check: a supervisor that cannot bind exits.

```json
{"op": "reconcile"}
{"op": "done", "installed": ["avatar_kanban"], "removed": [], "failed": []}
```

The app writes `plugins.json` first, then sends the request. `action` is optional.

| action | what the supervisor does |
| --- | --- |
| absent | install into the live venv. Anything whose files are held open is named in `failed` |
| `restart` | acknowledge and install nothing. The app saves and exits `75`; the supervisor reconciles with nothing running, then starts it again |
| `clean` | as `restart`, and the venv is cleared before the install |

Pure-python packages can be replaced while imported; loaded compiled extensions cannot, which
is the only thing a plain reconcile cannot do and the reason the other two exist.

## Process

| exit | meaning |
| --- | --- |
| `0` | closed. The supervisor exits too |
| `75` | reconcile, then start it again |
| anything else | crashed. Restart with backoff, `restarts` times within `window`, then give up |

The app is assigned to a job object so it dies with the supervisor.

## Files

| file | owner | read by |
| --- | --- | --- |
| `config.json` | installer | supervisor, app |
| `plugins.json` | installer seeds it, then the app | supervisor |
| `state.json` | supervisor | supervisor |
| `supervisor.log` | supervisor | — |

## Stdlib only

`asyncio`, `subprocess`, `json`, `hashlib`, `pathlib`, `logging.handlers`, and `ctypes` for the
job object. No interface: a first install is silent while it runs, and the log is the record.

## Out of scope

Reloading a plugin into the running app. Self-updating `supervisor.py` outside the installer.
Anything about what a plugin is.
