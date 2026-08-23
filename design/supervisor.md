# Supervisor — design

A single executable that turns a config file into a running python application on a machine that has no python. It provisions a private runtime in a workspace, installs what the config names, starts the declared processes and keeps them alive. It handles requirement strings and never plugins — what a plugin is stays inside the app.

Installing is downloading one `.bat`.

## Install

```bat
@echo off
setlocal
set "APP=example"
set "DIR=%LOCALAPPDATA%\%APP%"
set "BASE=https://github.com/example/example/releases/latest/download"

mkdir "%DIR%" 2>nul
curl -fsSL -o "%DIR%\supervisor.exe" "%BASE%/supervisor.exe" || goto :fail
curl -fsSL -o "%DIR%\config.json"    "%BASE%/config.json"    || goto :fail

if not exist "%DIR%\seed.json" >"%DIR%\seed.json" echo {"registries":["https://raw.githubusercontent.com/example/registry/main/registry.json"],"plugins":["example-notes","example-charts"]}

start "" "%DIR%\supervisor.exe"
exit /b 0

:fail
echo Install failed.
pause
exit /b 1
```

Two downloads, no admin, no python, no git. `curl.exe` ships with Windows 10 1803 and later. The workspace is the install directory, so uninstalling is deleting one folder.

**Releases live on GitHub**, so there is no server to run. `releases/latest/download/<asset>` redirects to the newest release, which keeps the `.bat` version-free — written once, works indefinitely.

**The `.bat` defines the bundle.** `seed.json` names the registries to start from and the plugins to install, and it is written only when absent, so re-running the installer never overwrites a user's choices. Publishing a different default set is publishing a different `.bat` — nothing else has to change, and nothing else has to be hosted. It is one line of JSON because `cmd` escaping punishes anything longer: `%`, `&`, `|`, `<` and `>` all need care inside `echo`, and plugin *names* avoid every one of them where full requirement strings would not.

**The supervisor never reads `seed.json`.** It is the app's file, consumed on first run — see [plugin_runtime.md](plugin_runtime.md). The first launch therefore installs only the config's own packages; the app then resolves the seed and asks for the rest through the ordinary live path, which is the same path every later plugin change takes.

**The installer is the updater.** Re-running it overwrites the executable and the config, both vendor-owned, and touches nothing else. The venv, the plugin list, the registries and the logs survive, and the next launch reconciles against the new config.

**The cost is SmartScreen.** An unsigned download warns on first run and only code signing fixes it. A `certutil -hashfile` check in the `.bat` is worth adding, but it defends against a broken mirror rather than a compromised host.

## Provisioning is delegated

The supervisor downloads no python, verifies no archive, creates no venv and resolves no dependency. **`uv` does all of it.** The only network code left is fetching `uv` itself — one zip, one checksum, `ZipFile.ExtractToDirectory` — and `uv` is confined to the workspace by `UV_PYTHON_INSTALL_DIR` and `UV_CACHE_DIR`.

Because `uv` owns an index of interpreter builds, the config names a version rather than a url:

```json
{
	"title": "Example",
	"uv": {
		"url": "https://github.com/astral-sh/uv/releases/download/0.12.5/uv-x86_64-pc-windows-msvc.zip",
		"sha256": "…"
	},
	"python": "3.13",
	"index": "",
	"packages": [
		"example-core==1.4.0",
		"example-host==1.4.0"
	],
	"processes": [
		{ "name": "app", "module": "example_host", "required": true, "restart": "on-failure", "maxRestarts": 3 }
	],
	"restartCode": 75,
	"pollSeconds": 1
}
```

A process is `module`, `script` or raw `args` — one of the three, resolved into a command at plan time, and always run unbuffered so its output reaches the log as it happens rather than when it ends.

**`packages` is trusted; `plugins.json` is not.** The allowlist below governs requirements the app supplies, because those originate in a registry somebody else wrote. The config is vendor-owned and arrives with the executable, so it may name a local directory — which is what makes a development install possible without a second code path.

**The child is told where its workspace is**, in `SUPERVISOR_WORKSPACE`. It has to write `plugins.json` and `request.json` somewhere, and the alternative is every app re-deriving a path the supervisor already knows.

## Files

Five that the supervisor touches, each with exactly one writer. That is the whole coordination design. The app keeps files of its own in the same folder — `seed.json`, the registry list, the registry cache — and the supervisor neither reads nor knows about any of them.

| file | owner | written by | read by |
| --- | --- | --- | --- |
| `config.json` | vendor | the installer | supervisor |
| `plugins.json` | the app | the app | supervisor |
| `request.json` | the app | the app | supervisor |
| `reply.json` | supervisor | supervisor | the app |
| `state.json` | supervisor | supervisor | supervisor |

**`state.json` is private** — fingerprints, phases, the last good requirement set. `reply.json` is not state but an answer: it says what became of one request and nothing else.

**Nothing is ever deleted and nobody writes another program's file.** Handled requests and stale replies stay on disk, and the revision they carry is what makes them stale. Single-writer survives without a handshake to negotiate it, and the last exchange is still there to read when something has gone wrong.

## plugins.json

The one file in the workspace the supervisor reads and does not own. The app writes it; the supervisor sees a revision and a list of requirement strings, and that is the entire extent of what it knows about plugins. Where they come from, what they do and who chose them are in [plugin_runtime.md](plugin_runtime.md).

```json
{
	"revision": 7,
	"requirements": [
		"example-notes==0.4.1",
		"example-charts @ https://github.com/someone/charts/releases/download/v1.2.0/example_charts-1.2.0-py3-none-any.whl#sha256=…"
	]
}
```

Entries are PEP 508 strings, checked against the allowlist below before anything acts on them. `revision` is an integer the app increments; it feeds the requirement fingerprint, so bumping it forces reconciliation even when every string is unchanged.

**Only the supervisor writes to the venv.** State describing an environment a second process can change is not state — so the app declares what it wants here and never installs anything itself.

## The exchange

`request.json` in, `reply.json` out, both by temp-file-and-rename so a reader never sees half a document. The whole conversation is plain text on disk, reproducible by hand, and it survives either side dying in the middle.

```json
// request.json
{ "op": "reconcile", "revision": 7, "loaded": ["example-core", "example-ui", "numpy"] }
```
```json
// reply.json
{ "revision": 7, "state": "done", "applied": ["example-notes"], "deferred": ["example-charts"], "failed": [], "restart": true }
```

**The request carries what only the app knows.** Resolution belongs to the supervisor, which owns `uv`; which distributions are currently imported can only be asked inside the process they are imported into. The supervisor intersects the two and applies only what does not touch loaded code — the reasoning is the gate in [plugin_runtime.md](plugin_runtime.md).

**Both sides poll.** `FileSystemWatcher` drops events when its buffer overflows, fires twice for one change and stops silently if its directory is replaced, so it is an optimisation and never the mechanism. A one-second timestamp check on one file costs nothing at a few requests a week.

**The revision decides what is current.** The app ignores a reply that does not carry the revision it waits for; the supervisor ignores a request whose revision it has already handled, recorded in its own state. Stale files are therefore harmless and nothing needs clearing at startup.

**The reply is written before the work, not after.** `{"state": "working", "step": "downloading example-charts"}` goes out immediately and is rewritten as the steps progress, ending at `done`. Progress arrives through the file the app already polls, and a request that never reaches a terminal state is visibly one that died.

**Deferred is not failed.** A requirement that could not be applied to the live process is left in `plugins.json` untouched, so the next start installs it through the ordinary path. The distinction matters to the caller: a failure is worth retracting, a deferral is already scheduled.

**Deferral is all-or-nothing within one request.** A resolution is a single answer over the whole set, so when it touches loaded code there is no honest way to say which requirement was to blame — everything pending is deferred together. Attributing it per requirement would mean resolving each one alone, and the coarse answer costs one restart rather than several.

## Requirements

A requirement string reaches `uv` only if it names PyPI or GitHub. Restricting the sources to two is what makes the difference between forwarding a string blindly and being able to refuse it. **Four forms are accepted**; anything else fails at plan time, before a byte is downloaded.

| form | pinned by | needs git |
| --- | --- | --- |
| `example-notes==0.4.1` | version | no |
| `example-charts @ https://github.com/o/r/releases/download/v1.2.0/example_charts-1.2.0-py3-none-any.whl#sha256=…` | checksum | no |
| `example-charts @ https://github.com/o/r/archive/refs/tags/v1.2.0.tar.gz` | tag | no |
| `example-charts @ git+https://github.com/o/r@a1b2c3d` | ref | yes |

Only the first two are verifiable: a version pin resolves through the index, and a `#sha256=` fragment is checked exactly as the interpreter download is. Which form a plugin should be published in is [plugin_runtime.md](plugin_runtime.md).

**Validation is an allowlist.** A bare name with a specifier, or a URL whose host is `github.com`. No other index, no `file://`, no arbitrary download host, and no requirement containing a newline or a leading dash — a line beginning with `-` inside a requirements file is an *option*, and `--index-url http://…` smuggled into a plugin entry would redirect the entire install. For the same reason requirements are passed to `uv` as arguments and never written to a requirements file.

**Git is needed only for the `git+` form**, so the `git --version` check is conditional and most users never meet it. When they do, the reporter says "this plugin needs git installed" rather than burying a resolver traceback in a log nobody opens.

**Private repositories are out.** Supporting them means holding a GitHub token, and a credential store is a different project.

**A moving ref is invisible to the fingerprint.** `@main` hashes the same tomorrow as today, so nothing reinstalls on its own. The supervisor does not chase it; `revision` exists so the app can force the reconciliation when it decides one is due.

**The trust boundary is the app.** A requirement can run build code, so whoever writes `plugins.json` runs code as the user. The supervisor adds no privilege it did not already have, and accepts a requirement list from the workspace file and nowhere else.

## Three phases

`plan → provision → supervise`, with one hard rule: **the plan is complete and validated before anything is downloaded.** Paths resolved, entry points checked for being expressible, policies parsed, requirement strings checked against the allowlist. A config error then costs nothing.

The plan is a value — uv path, python version, requirement set, resolved process commands. Provision makes the workspace match it, supervise executes it, and nothing afterwards reads a config file again except the requirement hash recomputed at each start.

## Provision

Layered, because the layers change at different rates, with a fingerprint each in `state.json`. One fingerprint over everything would re-download the interpreter every time a plugin version changed.

| layer | fingerprint over | rebuilt when |
| --- | --- | --- |
| uv | url + checksum | the pin moves |
| interpreter | version string | the version changes |
| venv | interpreter fingerprint | the interpreter changes |
| requirements | index + config packages + plugin requirements + revision | any of them changes |

**State records a phase, not just a hash** — `{ layer: "requirements", phase: "installing", fingerprint: "…" }`, written before the step and updated after. A launch finding any phase other than `ready` rebuilds that layer instead of resuming into it, because an interrupted install leaves a venv that looks finished and is not.

**Reconciliation runs before every start**, not only after a plugin change: hash `config.packages ∪ plugins.requirements`, compare against state, do nothing if it matches. That is one hash on a normal launch, and it means a crash-restart of an app that had just written `plugins.json` still comes back with a correct venv.

**Additive changes install; anything else rebuilds.** `uv pip install` never removes, so a plugin dropped from the list would linger forever. A purely additive diff installs the delta; a removal or a change deletes the venv and rebuilds it, which takes seconds from uv's cache and keeps the venv genuinely declarative.

**A failed install must not leave a dead app.** State keeps the last requirement set that produced a working venv; if reconciliation fails, the supervisor rebuilds that set and starts the app anyway. A typo in a plugin version never produces a launcher that refuses to launch.

**Failure is reported wherever someone is listening.** A live request gets a reply naming what failed. Reconciliation at start has nobody to answer, so the reporter names it in the window it is already showing — and the app, once running, can always see for itself which distributions are present.

**Everything stays in the workspace.** No global install, no user site-packages, no PATH mutation, no registry.

## Supervise

Processes start in declaration order and are independent afterward. No dependency graph — ordering the list is the config author's job, and a child that truly needs another one up has to retry anyway.

**Restart policy is per process**: `never`, `on-failure` (default), `always`, plus a rolling crash window — at most *N* restarts within *W* seconds, with exponential backoff, and the counter cleared once a process outlives the window. That is what separates a boot loop from a crash after six good hours; a lifetime counter treats them identically and spends the budget of the second on the first.

**Criticality decides what giving up means.** A `required` process exhausting its restarts stops everything and exits nonzero. A non-required one stays dead and logged while the rest keep running. When every required process has exited *cleanly*, the supervisor stops the others and exits zero — that is what closing the app looks like from here.

**The exit code carries one thing: restart.** Zero is a clean finish, one reserved code means *restart me*, everything else is failure. Because reconciliation runs at every start, that single code is enough to complete any change the live path deferred.

**Shutdown is asked for, then enforced** — children stopped in reverse start order, each with a grace period, then killed. The job object tying their lifetime to the supervisor is the backstop for the supervisor being force-killed, not the normal path; without it a force-kill orphans the children and the next launch produces a second copy of everything.

**One instance per workspace.** The lock is keyed by the workspace path and scoped to the user's session, so two workspaces coexist, another user is not blocked, and a second launch signals the running instance and exits instead of dying silently.

## Cross-cutting

**Reporting is an interface, not a window.** Provisioning is the only slow phase and the only one with anything to say; it emits progress to a reporter — window, console or silent — chosen at startup. The core carries no UI dependency, which is what lets one binary run headless and windowed.

**Failure before the first process is visible.** A windowed supervisor that writes a log line and exits is indistinguishable from a broken double-click, so every terminal failure in plan or provision reaches the reporter as well as the log.

**Logging.** One file in the workspace, rotated by size across a few generations rather than deleted at a threshold — a crash loop that fills a megabyte destroys the evidence of its own first failure. Every line carries its source: supervisor, provisioning, or a child's name. Child stdout and stderr are captured line by line, which for a windowless child is the only place its output exists.

**Platform lives behind two seams**: process-group lifetime and the name of the venv's script directory. Config, plan, fingerprints, the file exchange and restart policy are platform-neutral.

## Shape

| piece | job |
| --- | --- |
| `Program` | phases, exit codes |
| `Plan` | config + plugins → a validated launch plan |
| `Uv` | ensure uv, then `python install`, `venv`, `pip install` |
| `Runtime` | layer fingerprints, private state, reconciliation |
| `Exchange` | request in, reply out, revision bookkeeping |
| `Children` | N processes, restart policy, job object, shutdown |
| `Reporter` | window, console, silent |
| `Log` | rotating, source-tagged |

## Out of scope

Dependency ordering between processes. A socket, pipe or service interface — the file exchange is the channel, and it can be revisited if polling ever proves too slow. Resolving plugins from an index; the app does that. Self-update of the supervisor executable; the `.bat` is the updater.
