namespace Supervisor;

internal sealed class LayerState
{
	public string Fingerprint { get; set; } = "";
	public string Phase { get; set; } = "";

	public bool Ready(string fingerprint) => Phase == "ready" && Fingerprint == fingerprint;
}

/// <summary>The supervisor's own bookkeeping. Nothing else reads it.</summary>
internal sealed class State
{
	public LayerState Uv { get; set; } = new();
	public LayerState Python { get; set; } = new();
	public LayerState Venv { get; set; } = new();
	public LayerState Requirements { get; set; } = new();
	public List<string> Installed { get; set; } = new();
	public int HandledRevision { get; set; } = -1;

	private string __path = "";

	public static State Load(string path)
	{
		var state = Json.Read<State>(path) ?? new State();
		state.__path = path;
		return state;
	}

	public void Begin(LayerState layer, string fingerprint)
	{
		layer.Phase = "working";
		layer.Fingerprint = fingerprint;
		Save();
	}

	public void Done(LayerState layer)
	{
		layer.Phase = "ready";
		Save();
	}

	public void Save()
	{
		try
		{
			Json.WriteAtomic(__path, this);
		}
		catch (IOException)
		{
		}
	}
}
