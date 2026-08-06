using System.Diagnostics;

namespace AvatarLauncher;

internal static class Program
{
	private const string MutexName = @"Global\avatar_project.launcher";

	private static Process? __child;
	private static ProcessGroup? __group;

	[STAThread]
	private static int Main(string[] args)
	{
		using var single = new Mutex(true, MutexName, out var owned);
		if (!owned)
			return 0;

		var directory = ConfigDirectory(args);
		var options = Options.Load(directory);
		var log = new Log(options.LogPath);

		if (options.ConfigProblem is not null)
		{
			log.Write($"cannot start: {options.ConfigProblem}");
			return 2;
		}

		var bootstrap = Bootstrap.Load(Path.Combine(directory, Bootstrap.FileName), out var bootstrapProblem);
		if (bootstrapProblem is not null)
		{
			log.Write($"cannot start: {bootstrapProblem}");
			return 2;
		}

		var arguments = new List<string>();
		if (bootstrap is not null)
		{
			if (!Provision(bootstrap, log))
				return 4;
			options.Python = bootstrap.VenvPython;
			options.WorkingDirectory = bootstrap.Directory;
			arguments = bootstrap.EntryArguments();
		}
		else
		{
			arguments.Add(options.Script);
		}

		var problem = options.Validate(bootstrap is null);
		if (problem is not null)
		{
			log.Write($"cannot start: {problem}");
			return 2;
		}

		if (arguments.Count == 0)
		{
			log.Write("cannot start: nothing to run, set an entry module or script");
			return 2;
		}

		AppDomain.CurrentDomain.ProcessExit += (_, _) => Stop();

		using var group = new ProcessGroup();
		__group = group;

		log.Write($"launcher start: {options.Python} {string.Join(" ", arguments)}");

		var attempt = 0;
		while (true)
		{
			var code = Run(options, arguments, log);
			if (code == 0)
			{
				log.Write("avatar closed");
				return 0;
			}

			if (!options.RestartOnFailure || attempt >= options.MaxRestarts)
			{
				log.Write($"avatar failed with {code}, giving up after {attempt} restarts");
				return code;
			}

			attempt++;
			log.Write($"avatar failed with {code}, restart {attempt} of {options.MaxRestarts}");
			Thread.Sleep(TimeSpan.FromSeconds(options.RestartDelaySeconds));
		}
	}

	private static bool Provision(Bootstrap bootstrap, Log log)
	{
		if (bootstrap.IsReady())
		{
			log.Write("runtime is ready");
			return true;
		}

		var window = new ProgressWindow();
		var work = Task.Run(() =>
		{
			try
			{
				return bootstrap.Ensure(log, window.Report);
			}
			catch (Exception ex)
			{
				log.Write($"preparing the runtime failed: {ex}");
				return false;
			}
		});
		window.RunUntil(work);
		window.Dispose();

		if (work.Result)
			return true;

		log.Write("could not prepare the runtime");
		return false;
	}

	private static string ConfigDirectory(string[] args)
	{
		for (var i = 0; i < args.Length - 1; i++)
			if (args[i] is "--config" or "-c")
				return args[i + 1];
		return AppContext.BaseDirectory;
	}

	private static int Run(Options options, List<string> arguments, Log log)
	{
		var info = new ProcessStartInfo(options.Python)
		{
			WorkingDirectory = options.WorkingDirectory,
			UseShellExecute = false,
			CreateNoWindow = true,
			RedirectStandardOutput = true,
			RedirectStandardError = true,
		};
		foreach (var argument in arguments)
			info.ArgumentList.Add(argument);

		using var process = new Process { StartInfo = info, EnableRaisingEvents = true };
		process.OutputDataReceived += (_, args) =>
		{
			if (args.Data is not null)
				log.Write($"out | {args.Data}");
		};
		process.ErrorDataReceived += (_, args) =>
		{
			if (args.Data is not null)
				log.Write($"err | {args.Data}");
		};

		try
		{
			process.Start();
		}
		catch (Exception ex)
		{
			log.Write($"cannot start avatar: {ex.Message}");
			return 3;
		}

		__child = process;
		if (__group is not null && !__group.Add(process))
			log.Write("avatar is not tied to the launcher, it can outlive it");
		process.BeginOutputReadLine();
		process.BeginErrorReadLine();
		process.WaitForExit();
		__child = null;

		return process.ExitCode;
	}

	private static void Stop()
	{
		var child = __child;
		if (child is null || child.HasExited)
			return;
		try
		{
			child.Kill(true);
		}
		catch (Exception)
		{
		}
	}
}
