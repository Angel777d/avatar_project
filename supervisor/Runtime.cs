namespace Supervisor;

internal sealed class Plugins
{
	public int Revision { get; set; }
	public List<string> Requirements { get; set; } = new();
}

internal sealed class Reconciliation
{
	public bool Ok = true;
	public bool RestartNeeded;
	public List<string> Applied = new();
	public List<string> Deferred = new();
	public List<string> Failed = new();
	public string Error = "";
}

/// <summary>Owns the workspace: the layers, their fingerprints, and making the venv match what is wanted.</summary>
internal sealed class Runtime
{
	private readonly Plan __plan;
	private readonly State __state;
	private readonly Uv __uv;
	private readonly Log __log;

	public Runtime(Plan plan, State state, Uv uv, Log log)
	{
		__plan = plan;
		__state = state;
		__uv = uv;
		__log = log;
	}

	public Plugins ReadPlugins() => Json.Read<Plugins>(__plan.PluginsPath) ?? new Plugins();

	/// <summary>config packages first, then whatever the app asked for, deduplicated by name.</summary>
	public List<string> Desired(Plugins plugins)
	{
		var set = new List<string>();
		var seen = new HashSet<string>();
		foreach (var entry in __plan.Packages.Concat(plugins.Requirements))
		{
			var text = entry.Trim();
			if (text.Length > 0 && seen.Add(Requirements.Name(text)))
				set.Add(text);
		}
		return set;
	}

	/// <summary>The whole of provisioning, run before any child starts. Blocking, reports as it goes.</summary>
	public bool Provision(Action<string> progress, out string? problem)
	{
		problem = null;

		var uvPrint = Requirements.Fingerprint(__plan.UvSource.Url, __plan.UvSource.Sha256);
		if (!__state.Uv.Ready(uvPrint) || !File.Exists(__plan.UvExe))
		{
			__state.Begin(__state.Uv, uvPrint);
			if (!__uv.Ensure(progress))
			{
				problem = "could not prepare uv";
				return false;
			}
			__state.Done(__state.Uv);
		}

		var pythonPrint = Requirements.Fingerprint(__plan.PythonVersion, uvPrint);
		if (!__state.Python.Ready(pythonPrint))
		{
			progress($"Installing python {__plan.PythonVersion}");
			__state.Begin(__state.Python, pythonPrint);
			var result = __uv.InstallPython();
			if (!result.Ok)
			{
				problem = $"could not install python {__plan.PythonVersion}";
				return false;
			}
			__state.Done(__state.Python);
		}

		if (!__state.Venv.Ready(pythonPrint) || !File.Exists(__plan.VenvConsolePython))
		{
			progress("Preparing the environment");
			__state.Begin(__state.Venv, pythonPrint);
			if (!Rebuild())
			{
				problem = "could not create the environment";
				return false;
			}
			__state.Done(__state.Venv);
			__state.Installed.Clear();
			__state.Requirements.Phase = "";
			__state.Save();
		}

		var plugins = ReadPlugins();
		var outcome = Reconcile(plugins, null, progress);
		if (outcome.Ok)
			return true;

		problem = outcome.Error;
		return true; // a bad requirement never stops the app from starting
	}

	/// <summary>
	/// Make the venv match the desired set. <paramref name="loaded"/> non-null means a live request:
	/// anything the resolution would touch that is already imported is deferred instead of applied.
	/// </summary>
	public Reconciliation Reconcile(Plugins plugins, HashSet<string>? loaded, Action<string> progress)
	{
		var outcome = new Reconciliation();
		var desired = Desired(plugins);

		foreach (var requirement in plugins.Requirements)
		{
			if (Requirements.Validate(requirement) is not { } problem)
				continue;
			__log.Write("prov", $"refused: {problem}");
			outcome.Failed.Add(requirement);
			outcome.Ok = false;
			outcome.Error = problem;
			desired.Remove(requirement);
		}

		if (desired.Any(Requirements.NeedsGit) && !HasGit())
		{
			var failing = desired.Where(Requirements.NeedsGit).ToList();
			foreach (var entry in failing)
			{
				outcome.Failed.Add(entry);
				desired.Remove(entry);
			}
			outcome.Ok = false;
			outcome.Error = "these need git installed";
			__log.Write("prov", "git is not on PATH, skipping requirements that need it");
		}

		var print = Requirements.Fingerprint(__plan.Index, desired, plugins.Revision);
		if (__state.Requirements.Ready(print))
			return outcome;

		var previous = new HashSet<string>(__state.Installed.Select(Requirements.Name));
		var next = desired.Select(Requirements.Name).ToHashSet();
		var additive = previous.IsSubsetOf(next) && __state.Installed.All(desired.Contains);

		if (loaded is not null)
		{
			var touched = __uv.WouldTouch(desired);
			if (touched is null || touched.Overlaps(loaded) || !additive)
			{
				outcome.Deferred.AddRange(desired.Where(entry => !__state.Installed.Contains(entry)));
				outcome.RestartNeeded = outcome.Deferred.Count > 0;
				__log.Write($"deferred {outcome.Deferred.Count} requirement(s) to the next start");
				return outcome;
			}
		}

		__state.Begin(__state.Requirements, print);

		if (!additive)
		{
			progress("Rebuilding the environment");
			if (!Rebuild())
			{
				outcome.Ok = false;
				outcome.Error = "could not rebuild the environment";
				return outcome;
			}
		}

		progress($"Installing {desired.Count} package(s)");
		var install = __uv.Install(desired, false);
		if (!install.Ok)
		{
			outcome.Ok = false;
			outcome.Error = Reason(install);
			__log.Write("prov", "install failed, falling back to the last good set");
			Recover(progress);
			return outcome;
		}

		outcome.Applied.AddRange(desired.Where(entry => !__state.Installed.Contains(entry)));
		__state.Installed = desired;
		__state.Done(__state.Requirements);
		progress("Ready");
		return outcome;
	}

	public void MarkHandled(int revision)
	{
		__state.HandledRevision = revision;
		__state.Save();
	}

	public int HandledRevision => __state.HandledRevision;

	private void Recover(Action<string> progress)
	{
		if (__state.Installed.Count == 0)
			return;
		progress("Restoring the last working set");
		if (!Rebuild())
			return;
		var install = __uv.Install(__state.Installed, false);
		if (install.Ok)
			__state.Done(__state.Requirements);
	}

	private bool Rebuild()
	{
		try
		{
			if (Directory.Exists(__plan.VenvDirectory))
				Directory.Delete(__plan.VenvDirectory, true);
		}
		catch (Exception ex)
		{
			__log.Write("prov", $"could not remove the environment: {ex.Message}");
			return false;
		}

		__state.Installed.Clear();
		return __uv.CreateVenv().Ok;
	}

	private static string Reason(UvResult result)
	{
		var line = result.Output.LastOrDefault(entry => entry.Contains("error", StringComparison.OrdinalIgnoreCase));
		return line?.Trim() ?? "the installer failed";
	}

	private static bool HasGit()
	{
		try
		{
			using var process = System.Diagnostics.Process.Start(new System.Diagnostics.ProcessStartInfo("git", "--version")
			{
				UseShellExecute = false,
				CreateNoWindow = true,
				RedirectStandardOutput = true,
				RedirectStandardError = true,
			});
			if (process is null)
				return false;
			process.WaitForExit(5000);
			return process.HasExited && process.ExitCode == 0;
		}
		catch (Exception)
		{
			return false;
		}
	}
}
