namespace Supervisor;

internal sealed class Request
{
	public string Op { get; set; } = "";
	public int Revision { get; set; }
	public List<string> Loaded { get; set; } = new();
}

internal sealed class Reply
{
	public int Revision { get; set; }
	public string State { get; set; } = "working";
	public string Step { get; set; } = "";
	public List<string> Applied { get; set; } = new();
	public List<string> Deferred { get; set; } = new();
	public List<string> Failed { get; set; } = new();
	public bool Restart { get; set; }
	public string Error { get; set; } = "";
}

/// <summary>request.json in, reply.json out. Nothing is deleted; the revision decides what is current.</summary>
internal sealed class Exchange
{
	private readonly Plan __plan;
	private readonly Runtime __runtime;
	private readonly Log __log;

	private DateTime __seen = DateTime.MinValue;

	public Exchange(Plan plan, Runtime runtime, Log log)
	{
		__plan = plan;
		__runtime = runtime;
		__log = log;
	}

	public void Poll()
	{
		DateTime written;
		try
		{
			if (!File.Exists(__plan.RequestPath))
				return;
			written = File.GetLastWriteTimeUtc(__plan.RequestPath);
		}
		catch (IOException)
		{
			return;
		}

		if (written == __seen)
			return;
		__seen = written;

		var request = Json.Read<Request>(__plan.RequestPath);
		if (request is null)
		{
			__log.Write("request.json is not readable, ignoring it");
			return;
		}

		if (request.Revision <= __runtime.HandledRevision)
			return;

		if (!request.Op.Equals("reconcile", StringComparison.OrdinalIgnoreCase))
		{
			__log.Write($"unknown request \"{request.Op}\", ignoring it");
			return;
		}

		Handle(request);
	}

	private void Handle(Request request)
	{
		__log.Write($"request: reconcile to revision {request.Revision}");

		var reply = new Reply { Revision = request.Revision, State = "working", Step = "Reading the plugin list" };
		Write(reply);

		var plugins = __runtime.ReadPlugins();
		if (plugins.Revision != request.Revision)
			__log.Write($"plugins.json is at revision {plugins.Revision}, the request asked for {request.Revision}");

		var loaded = request.Loaded.Select(Requirements.Normalize).ToHashSet();

		Reconciliation outcome;
		try
		{
			outcome = __runtime.Reconcile(plugins, loaded, step =>
			{
				reply.Step = step;
				Write(reply);
			});
		}
		catch (Exception ex)
		{
			__log.Write($"reconciliation threw: {ex.Message}");
			outcome = new Reconciliation { Ok = false, Error = ex.Message };
		}

		reply.State = "done";
		reply.Step = "";
		reply.Applied = outcome.Applied;
		reply.Deferred = outcome.Deferred;
		reply.Failed = outcome.Failed;
		reply.Restart = outcome.RestartNeeded;
		reply.Error = outcome.Error;
		Write(reply);

		__runtime.MarkHandled(request.Revision);
		__log.Write($"reply: applied {outcome.Applied.Count}, deferred {outcome.Deferred.Count}, failed {outcome.Failed.Count}");
	}

	private void Write(Reply reply)
	{
		try
		{
			Json.WriteAtomic(__plan.ReplyPath, reply);
		}
		catch (IOException ex)
		{
			__log.Write($"could not write reply.json: {ex.Message}");
		}
	}
}
