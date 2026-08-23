using System.Text.Json;

namespace Supervisor;

internal sealed class UvSource
{
	public string Url { get; set; } = "";
	public string Sha256 { get; set; } = "";
}

internal sealed class ProcessEntry
{
	public string Name { get; set; } = "";
	public string Module { get; set; } = "";
	public string Script { get; set; } = "";
	public List<string> Args { get; set; } = new();
	public bool Required { get; set; }
	public string Restart { get; set; } = "on-failure";
	public int MaxRestarts { get; set; } = 3;
	public double WindowSeconds { get; set; } = 60;
	public double BackoffSeconds { get; set; } = 2;
	public double BackoffMaxSeconds { get; set; } = 60;
	public double StopGraceSeconds { get; set; } = 5;
}

internal sealed class Config
{
	public const string FileName = "config.json";

	public string Title { get; set; } = "Supervisor";
	public UvSource Uv { get; set; } = new();
	public string Python { get; set; } = "";
	public string Index { get; set; } = "";
	public List<string> Packages { get; set; } = new();
	public List<ProcessEntry> Processes { get; set; } = new();
	public int RestartCode { get; set; } = 75;
	public double PollSeconds { get; set; } = 1;

	public static Config? Load(string path, out string? problem)
	{
		problem = null;
		if (!File.Exists(path))
		{
			problem = $"{FileName} not found beside the executable";
			return null;
		}

		try
		{
			var config = JsonSerializer.Deserialize<Config>(File.ReadAllText(path), Json.Options);
			if (config is null)
				problem = $"{FileName} is empty";
			return config;
		}
		catch (Exception ex)
		{
			problem = $"{FileName} is not readable: {ex.Message}";
			return null;
		}
	}
}

internal static class Json
{
	public static readonly JsonSerializerOptions Options = new()
	{
		PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
		PropertyNameCaseInsensitive = true,
		ReadCommentHandling = JsonCommentHandling.Skip,
		AllowTrailingCommas = true,
		WriteIndented = true,
	};

	public static void WriteAtomic(string path, object value)
	{
		var temp = path + ".tmp";
		File.WriteAllText(temp, JsonSerializer.Serialize(value, Options));
		File.Move(temp, path, true);
	}

	public static T? Read<T>(string path) where T : class
	{
		if (!File.Exists(path))
			return null;
		try
		{
			return JsonSerializer.Deserialize<T>(File.ReadAllText(path), Options);
		}
		catch (Exception)
		{
			return null;
		}
	}
}
