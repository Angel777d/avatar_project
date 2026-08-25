# Runtime plugin updates — design

Install, update and remove a plugin without restarting. The supervisor does the installing and the file exchange that carries the request is in [supervisor.md](supervisor.md); everything here is what the app does around it. What this buys is that the restart stops being the normal case — and the exception has to be named precisely, because the three operations differ enormously in how safe they are.

## Who does what

The app never installs anything. It decides, it introspects, and it swaps modules; the supervisor resolves and writes to the venv, because it owns `uv` and because an environment two processes can change cannot be described by either one's state. Any change runs the same four steps:

1. The app writes `plugins.json` — the desired state, on disk before anything acts on it.
2. The app writes `request.json`, naming the revision and the distributions it currently has imported.
3. The supervisor resolves, applies what the gate allows, and writes `reply.json` — progress while it works, then what was applied, deferred and failed.
4. The app, polling that file, unloads and reloads the applied plugins and tells the user which deferred ones are waiting for a restart.

**`plugins.json` is written first, always** — before the request, before the resolution. An app that asks first and records afterwards can be killed in between, leaving a venv holding something the desired state never mentioned, to be discarded the next time it is rebuilt.

**On a failure the app reverts the file; on a deferral it must not.** A failed requirement left in place is retried at every launch forever. A deferred one is a change that is going to happen at the next start, and removing it would cancel it.

**Polling is not a background thread's problem to hide.** The request came from a button, so a timer reading one file a second and feeding the step straight into the dialog that started it is the whole implementation. The same dialog shows the failure if there is one.

**One process asks.** With several children configured, exactly one owns plugin management — two apps writing a desired state into the same file is a race nothing arbitrates.

## Registries

**The app owns all of this** — discovery, the catalogue, the user interface, deciding what should be installed. The supervisor sees requirement strings and a revision and nothing else.

**Discovery has no API to lean on.** PyPI has no search endpoint, and enumerating its simple index by name prefix is neither cheap nor trustworthy since nobody owns a prefix. So a registry is a document somebody curates, and there can be several: an official one, a community one, a company's internal one, a file on disk while a plugin is being written.

`registries.json`, in the workspace, is the list. It is the app's file and nothing else reads it.

```json
{
	"registries": [
		{ "name": "official", "url": "https://raw.githubusercontent.com/example/registry/main/registry.json" },
		{ "name": "dev",      "path": "D:/work/my-plugin/registry.json" }
	]
}
```

**It changes when a registry is added or removed, and at no other time.** There is no enabled flag, no last-fetched timestamp, no per-registry state — a source is present or it is not. Everything that varies during normal use lives elsewhere, which keeps this a short list a person can read and edit by hand and keeps the app from writing to it behind their back.

**A registry lists what is available; `plugins.json` says what is wanted.** The app reads every registry, presents the union as a catalogue, and writes into `plugins.json` the requirements for exactly those the user chose. Turning a plugin on is adding its requirement; turning it off is removing it, which the next reconciliation uninstalls. There is no third state and nothing is installed but idle — what is in `plugins.json` is what exists in the venv, and what is in a registry is only what could.

A registry has a `url` or a `path`, never both. **A local file is read fresh every time** — the point of one is that an author edits it and reloads — while **a remote one is cached in the workspace with its ETag**, refreshed on start and on demand, and falls back to the cached copy whenever the fetch fails. A registry that has never been fetched is simply missing from the catalogue with a note saying so. Nothing about the plugin page waits on the network.

**A registry holds whatever mix of sources it likes.** PyPI and GitHub entries sit side by side in one document with no distinction — the difference lives entirely inside the requirement string, and every form is checked by the supervisor's allowlist regardless of which registry proposed it. That is the containment worth understanding when adding one: a registry chooses *what* to offer, never *where* it may be fetched from.

```json
{
	"name": "Example plugins",
	"version": 1,
	"plugins": [ … ]
}
```

**Order decides collisions.** Two registries offering the same plugin name is normal — a fork, a fresher build, a local copy of something official. The first in the list wins, and the interface always shows which registry an entry came from. No voting, no merging of entries, nothing that depends on fetch timing.

**Precedence is decided at runtime, never stored.** The file is appended to on add and cut from on remove, and is never rewritten to reorder — that is the third kind of write it does not have. The app builds the order when it loads the registries: a local path outranks a remote one, and otherwise they rank as they appear in the file, which is the order they were added. A developer's local registry therefore overrides the official entry for the same plugin without anyone configuring anything, because that is the only reason to have pointed at a file on disk.

The interface may reorder the list within a session, and that decides which entry wins while the app runs. It is not written back — the next launch recomputes the same default from the rule, so precedence never depends on a state nobody remembers setting.

**Adding a registry is a trust decision, and should read like one.** Anything it offers can run build code on the machine as the user. The allowlist bounds the damage to GitHub and PyPI, but does not make an unknown registry safe.

**Removing a registry uninstalls nothing.** The two files are independent: dropping a source does not touch what was chosen from it, so the plugin keeps working and only its updates stop being discoverable — worth saying in the interface rather than leaving to be noticed. Removing a *plugin* is the other file, and does uninstall it.

## The catalogue entry

One element of a registry's `plugins` array — what is known about a plugin before it is installed.

```json
{
	"name": "example-charts",
	"title": "Charts",
	"summary": "Plots over the log.",
	"version": "1.2.0",
	"requirement": "example-charts @ https://github.com/o/r/releases/download/v1.2.0/example_charts-1.2.0-py3-none-any.whl#sha256=…",
	"homepage": "https://github.com/o/r",
	"restartNeeded": false
}
```

**`restartNeeded` is a promise by the author, for the user interface.** It means *changing or removing this plugin once loaded requires a restart* — installing never does, since nothing of a new plugin is loaded yet, so the flag concerns the second time a plugin is touched and not the first. An author sets it when they ship a compiled extension, or when they know their plugin hands out objects that outlive it.

**It is advisory; the gate is authoritative.** The flag exists so the button can read "Update (restart required)" before the click rather than after. An author who forgets it is caught by the gate and by the unload failing; one who sets it needlessly costs a restart nobody needed. It decides nothing except what the user is told.

## Publishing a plugin

**Publish as a GitHub release wheel.** Of the four forms the supervisor accepts, that one carries a `#sha256=` fragment, so a plugin is verified exactly as the interpreter is; it installs without building, so no third-party `setup.py` runs on a user's machine; and it needs no git. An archive at a tag is the same thing without the integrity guarantee. `git+` exists for development and branch-tracking, which is the only thing the others cannot do — and a branch ref hashes the same tomorrow as today, so nothing reinstalls until the app increments `revision` to say an update is due. That is what makes "update this plugin" work for a moving ref without the supervisor understanding git.

**The built-in catalogue is the one exception, and omits the fragment.** It ships inside `avatar_manager` and names wheels built by the same release, so their hashes do not exist when it is packaged. A registry hosted separately, published after the wheels it points at, has no such excuse.

## What python actually allows

**There is no unload.** Removing a name from `sys.modules` drops one reference to a module object; it does not free the code. Every instance keeps its class, every closure keeps its globals, every registered callback keeps its function, and each of those keeps the module. "Unload" means *stop using and drop every reference*, which is a property of the plugin's discipline and not of anything the interpreter offers.

**Extension modules never unload at all.** A `.pyd` or `.dll` stays mapped until the process ends — CPython does not unload them, and Windows will not let a mapped file be replaced. This is a wall: **a plugin with a compiled extension anywhere in its dependency tree can never be updated or removed in place.**

**Pure python files are not held open.** The import machinery reads a `.py`, compiles it and closes the file, so overwriting it succeeds. That asymmetry is the whole reason this works: pure-python plugins are hot-swappable, binary ones are not.

**`importlib.reload` is the wrong tool.** It re-executes a module into the same namespace, leaves existing instances bound to the old classes and ignores submodules. Purging by prefix from `sys.modules` and importing fresh is the correct primitive, and it is only correct once the references are gone.

## The three operations

**Install is genuinely free.** Nothing from the new distribution is imported, so no file is held and nothing has to be torn down. Once the supervisor answers, the app calls `importlib.invalidate_caches()` so the new `.dist-info` becomes visible, re-queries the entry points and starts the plugin's systems.

**Update is unload → replace → load.** Stop the plugin's systems, drop every reference the host holds, purge its module tree from `sys.modules`, let the supervisor install the new version, invalidate caches, import again. The unload comes first even though nothing forces it to: pure python files are not locked, so old code could run against new files on disk, and that is a state worth never entering.

**Remove is unload without the reload.** Same constraints, and a leaked reference is a leak rather than a crash — the code stays resident, doing nothing, until the next restart.

## The gate

The danger is never the plugin's own files. It is the **transitive dependency it drags in**: a new plugin wanting a newer version of a library the process imported an hour ago makes the installer upgrade that library under a running interpreter, silently replacing pure-python parts while old code executes from memory, and failing halfway on the compiled ones.

> Resolve the requested change against the current venv. If it adds, changes or removes **any distribution already imported in the app's process**, the operation cannot be done live.

The test is mechanical, and it is split across the two programs because neither half is available to one of them: the resolver reports what would be touched and lives in the supervisor, `importlib.metadata` reports what is loaded and can only be asked inside the app. The request carries the loaded set, the supervisor intersects it with the resolution, and the intersection decides. A dry run costs a second and prevents a failure that corrupts an installation rather than merely failing.

## The unload contract

A plugin is hot-swappable only if it can be fully torn down, and that is a contract it satisfies rather than something the host can enforce:

- Everything it creates, it can destroy — systems stopped, listeners removed, menu entries and pages withdrawn, timers cancelled.
- Nothing it hands out outlives it. An object of one of its classes held by another plugin pins the old module forever.
- UI objects are destroyed on the toolkit's side, not merely dereferenced, and every signal connection into the plugin is dropped first — a callback into a torn-down plugin is a crash, not a leak.
- No compiled extension anywhere in its dependency tree.

The host tracks, per plugin, the distribution that provides it and the top-level modules that distribution installed — the metadata knows both — so a purge knows which prefixes to remove and can report what it could not.

**A plugin that fails the contract degrades, it does not break.** If a reference survives the purge the new version cannot take effect, and the answer is to leave the old one running and fall back to a restart, never to import a second copy alongside the first.

## What still needs a restart

- The core, always — it holds the references everything else is unloaded *from*, and cannot tear itself down.
- The UI framework when the update touches it, which it usually does, since it is the thing showing the progress of the update.
- Anything the gate rejects.
- Any plugin with a compiled extension in its tree.
- Any unload that leaves references behind.

The restart path is already built: write `plugins.json`, exit with the reserved code, let the supervisor reconcile. Falling back to it is one line and never a dead end, which is what makes the live path safe to attempt at all.
