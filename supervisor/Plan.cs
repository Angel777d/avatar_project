namespace Supervisor;

internal sealed class ProcessPlan
{
	public string Name = "";
	public List<string> Arguments = new();
	public bool Required;
	public string Restart = "on-failure";
	public int MaxRestarts;
	public TimeSpan Window;
	public TimeSpan Backoff;
	public TimeSpan BackoffMax;
	public TimeSpan StopGrace;
}

internal sealed class Plan
{
	public string Workspace = "";
	public string Title = "Supervisor";
	public UvSource UvSource = new();
	public string PythonVersion = "";
	public string Index = "";
	public List<string> Packages = new();
	public List<ProcessPlan> Processes = new();
	public int RestartCode = 75;
	public TimeSpan Poll = TimeSpan.FromSeconds(1);

	public string UvHome => Path.Combine(Workspace, "uv");
	public string UvExe => Path.Combine(UvHome, "uv.exe");
	public string PythonHome => Path.Combine(Workspace, "python");
	public string VenvDirectory => Path.Combine(Workspace, ".venv");
	public string VenvPython => Path.Combine(VenvDirectory, "Scripts", "pythonw.exe");
	public string VenvConsolePython => Path.Combine(VenvDirectory, "Scripts", "python.exe");
	public string StatePath => Path.Combine(Workspace, "state.json");
	public string PluginsPath => Path.Combine(Workspace, "plugins.json");
	public string RequestPath => Path.Combine(Workspace, "request.json");
	public string ReplyPath => Path.Combine(Workspace, "reply.json");
	public string LogPath => Path.Combine(Workspace, "supervisor.log");

	/// <summary>Everything is resolved and checked here, before a byte is downloaded.</summary>
	public static Plan? Build(Config config, string workspace, out string? problem)
	{
		problem = null;
		var plan = new Plan
		{
			Workspace = workspace,
			Title = config.Title,
			UvSource = config.Uv,
			PythonVersion = config.Python.Trim(),
			Index = config.Index.Trim(),
			Packages = config.Packages,
			RestartCode = config.RestartCode,
			Poll = TimeSpan.FromSeconds(Math.Clamp(config.PollSeconds, 0.2, 60)),
		};

		if (plan.UvSource.Url.Trim().Length == 0)
			problem = "no uv url configured";
		else if (plan.UvSource.Sha256.Trim().Length == 0)
			problem = "no uv checksum configured, refusing to download it";
		else if (plan.PythonVersion.Length == 0)
			problem = "no python version configured";
		else if (config.Processes.Count == 0)
			problem = "no processes configured, there is nothing to run";

		if (problem is not null)
			return null;

		foreach (var entry in config.Processes)
		{
			var arguments = Arguments(entry);
			if (arguments.Count == 0)
			{
				problem = $"process \"{entry.Name}\" has no module, script or args";
				return null;
			}

			if (entry.Restart is not ("never" or "on-failure" or "always"))
			{
				problem = $"process \"{entry.Name}\" has an unknown restart policy \"{entry.Restart}\"";
				return null;
			}

			plan.Processes.Add(new ProcessPlan
			{
				Name = entry.Name.Length > 0 ? entry.Name : "app",
				Arguments = arguments,
				Required = entry.Required,
				Restart = entry.Restart,
				MaxRestarts = Math.Max(0, entry.MaxRestarts),
				Window = TimeSpan.FromSeconds(Math.Max(1, entry.WindowSeconds)),
				Backoff = TimeSpan.FromSeconds(Math.Max(0, entry.BackoffSeconds)),
				BackoffMax = TimeSpan.FromSeconds(Math.Max(1, entry.BackoffMaxSeconds)),
				StopGrace = TimeSpan.FromSeconds(Math.Max(0, entry.StopGraceSeconds)),
			});
		}

		if (!plan.Processes.Any(process => process.Required))
		{
			problem = "no process is marked required, so nothing decides when to exit";
			return null;
		}

		return plan;
	}

	private static List<string> Arguments(ProcessEntry entry)
	{
		if (entry.Module.Trim().Length > 0)
			return new List<string> { "-u", "-m", entry.Module.Trim() };
		if (entry.Script.Trim().Length > 0)
			return new List<string> { "-u", Environment.ExpandEnvironmentVariables(entry.Script.Trim()) };
		return entry.Args.Count > 0 ? new List<string>(entry.Args) : new List<string>();
	}
}
