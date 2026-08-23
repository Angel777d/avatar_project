namespace Supervisor;

internal static class Program
{
	private static Children? __children;

	[STAThread]
	private static int Main(string[] args)
	{
		var workspace = Argument(args, "--workspace") ?? AppContext.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar);
		var reporter = Pick(args, "Supervisor");

		using var single = new Mutex(false, $"Local\\supervisor.{Requirements.Fingerprint(workspace.ToLowerInvariant())}", out _);
		if (!single.WaitOne(0))
			return 0;

		var log = new Log(Path.Combine(workspace, "supervisor.log"));

		var config = Config.Load(Path.Combine(workspace, Config.FileName), out var problem);
		if (config is null || problem is not null)
			return Refuse(log, reporter, problem ?? "the configuration is unusable");

		var plan = Plan.Build(config, workspace, out problem);
		if (plan is null || problem is not null)
			return Refuse(log, reporter, problem ?? "the configuration is unusable");

		if (reporter is WindowReporter)
			reporter = new WindowReporter(plan.Title);

		log.Write($"supervisor start in {workspace}");

		var state = State.Load(plan.StatePath);
		var uv = new Uv(plan, log);
		var runtime = new Runtime(plan, state, uv, log);
		var exchange = new Exchange(plan, runtime, log);

		using var group = new ProcessGroup();
		AppDomain.CurrentDomain.ProcessExit += (_, _) => __children?.Stop();

		while (true)
		{
			string? trouble = null;
			var ok = false;
			reporter.Run(Task.Run(() =>
			{
				try
				{
					ok = runtime.Provision(reporter.Step, out trouble);
				}
				catch (Exception ex)
				{
					log.Write($"provisioning threw: {ex}");
					trouble = ex.Message;
				}
			}));

			if (!ok)
				return Refuse(log, reporter, trouble ?? "could not prepare the runtime");
			if (trouble is not null)
				reporter.Fail(trouble);

			var children = new Children(plan, log, group);
			__children = children;
			children.Start();

			while (children.End == SessionEnd.Running)
			{
				exchange.Poll();
				Thread.Sleep(plan.Poll);
			}

			children.Stop();
			__children = null;

			switch (children.End)
			{
				case SessionEnd.Closed:
					log.Write("closed");
					return 0;
				case SessionEnd.GaveUp:
					log.Write($"giving up with {children.Code}");
					return children.Code == 0 ? 1 : children.Code;
				default:
					log.Write("restarting");
					continue;
			}
		}
	}

	private static int Refuse(Log log, IReporter reporter, string problem)
	{
		log.Write($"cannot start: {problem}");
		reporter.Fail($"Cannot start: {problem}");
		return 2;
	}

	private static IReporter Pick(string[] args, string title)
	{
		if (args.Contains("--silent"))
			return new SilentReporter();
		return args.Contains("--console") ? new ConsoleReporter() : new WindowReporter(title);
	}

	private static string? Argument(string[] args, string name)
	{
		for (var index = 0; index < args.Length - 1; index++)
			if (args[index] == name)
				return args[index + 1];
		return null;
	}
}
