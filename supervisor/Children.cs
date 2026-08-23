using System.Diagnostics;

namespace Supervisor;

internal enum SessionEnd
{
	Running,
	Closed,      // every required process finished cleanly
	RestartAsked,
	GaveUp,
}

/// <summary>One run of the declared processes. Restart policy lives per child; the session ends when a required one decides it.</summary>
internal sealed class Children
{
	private readonly Plan __plan;
	private readonly Log __log;
	private readonly ProcessGroup __group;

	private readonly List<Child> __children = new();

	public Children(Plan plan, Log log, ProcessGroup group)
	{
		__plan = plan;
		__log = log;
		__group = group;
	}

	public SessionEnd End { get; private set; } = SessionEnd.Running;
	public int Code { get; private set; }

	public void Start()
	{
		foreach (var process in __plan.Processes)
		{
			var child = new Child(process, __plan, __log, __group, Finish);
			__children.Add(child);
			child.Start();
		}
	}

	public void Stop()
	{
		foreach (var child in Enumerable.Reverse(__children))
			child.Stop();
	}

	private void Finish(Child child, SessionEnd end, int code)
	{
		if (!child.Plan.Required)
		{
			__log.Write($"{child.Plan.Name} is done and is not required, carrying on");
			return;
		}

		lock (__children)
		{
			if (End != SessionEnd.Running)
				return;

			if (end == SessionEnd.Closed && __children.Any(other => other.Plan.Required && other.Alive))
				return;

			End = end;
			Code = code;
		}
	}
}

internal sealed class Child
{
	private readonly Log __log;
	private readonly ProcessGroup __group;
	private readonly Plan __plan;
	private readonly Action<Child, SessionEnd, int> __finished;

	private readonly List<DateTime> __restarts = new();
	private volatile Process? __process;
	private volatile bool __stopping;
	private Thread? __thread;

	public Child(ProcessPlan plan, Plan root, Log log, ProcessGroup group, Action<Child, SessionEnd, int> finished)
	{
		Plan = plan;
		__plan = root;
		__log = log;
		__group = group;
		__finished = finished;
	}

	public ProcessPlan Plan { get; }
	public bool Alive => __process is { HasExited: false };

	public void Start()
	{
		__thread = new Thread(Loop) { IsBackground = true, Name = Plan.Name };
		__thread.Start();
	}

	public void Stop()
	{
		__stopping = true;
		var process = __process;
		if (process is null || process.HasExited)
			return;

		try
		{
			__log.Write($"stopping {Plan.Name}");
			process.CloseMainWindow();
			if (!process.WaitForExit((int)Plan.StopGrace.TotalMilliseconds))
				process.Kill(true);
		}
		catch (Exception)
		{
		}
	}

	private void Loop()
	{
		var backoff = Plan.Backoff;

		while (!__stopping)
		{
			var started = DateTime.UtcNow;
			var code = RunOnce();
			var uptime = DateTime.UtcNow - started;

			if (__stopping)
				return;

			if (code == __plan.RestartCode)
			{
				__log.Write($"{Plan.Name} asked to be restarted");
				__finished(this, SessionEnd.RestartAsked, 0);
				return;
			}

			if (code == 0)
			{
				__log.Write($"{Plan.Name} closed");
				if (Plan.Restart != "always")
				{
					__finished(this, SessionEnd.Closed, 0);
					return;
				}
			}
			else if (Plan.Restart == "never")
			{
				__log.Write($"{Plan.Name} failed with {code} and is not restarted");
				__finished(this, SessionEnd.GaveUp, code);
				return;
			}

			if (uptime > Plan.Window)
			{
				__restarts.Clear();
				backoff = Plan.Backoff;
			}

			__restarts.Add(DateTime.UtcNow);
			__restarts.RemoveAll(moment => DateTime.UtcNow - moment > Plan.Window);

			if (__restarts.Count > Plan.MaxRestarts)
			{
				__log.Write($"{Plan.Name} failed {__restarts.Count} times in {Plan.Window.TotalSeconds:0}s, giving up");
				__finished(this, SessionEnd.GaveUp, code == 0 ? 1 : code);
				return;
			}

			__log.Write($"{Plan.Name} exited with {code}, restart {__restarts.Count} of {Plan.MaxRestarts} in {backoff.TotalSeconds:0.#}s");
			Thread.Sleep(backoff);
			backoff = TimeSpan.FromSeconds(Math.Min(Plan.BackoffMax.TotalSeconds, Math.Max(1, backoff.TotalSeconds * 2)));
		}
	}

	private int RunOnce()
	{
		var info = new ProcessStartInfo(__plan.VenvPython)
		{
			WorkingDirectory = __plan.Workspace,
			UseShellExecute = false,
			CreateNoWindow = true,
			RedirectStandardOutput = true,
			RedirectStandardError = true,
		};
		foreach (var argument in Plan.Arguments)
			info.ArgumentList.Add(argument);

		info.Environment["PYTHONIOENCODING"] = "utf-8";
		info.Environment["SUPERVISOR_WORKSPACE"] = __plan.Workspace;

		using var process = new Process { StartInfo = info };
		process.OutputDataReceived += (_, args) => Line(args.Data);
		process.ErrorDataReceived += (_, args) => Line(args.Data);

		try
		{
			process.Start();
		}
		catch (Exception ex)
		{
			__log.Write($"cannot start {Plan.Name}: {ex.Message}");
			return -1;
		}

		__process = process;
		if (!__group.Add(process))
			__log.Write($"{Plan.Name} is not tied to the supervisor, it can outlive it");

		process.BeginOutputReadLine();
		process.BeginErrorReadLine();
		process.WaitForExit();
		__process = null;
		return process.ExitCode;
	}

	private void Line(string? text)
	{
		if (text is not null)
			__log.Write(Plan.Name, text);
	}
}
