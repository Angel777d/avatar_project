using System.Text.Json;

namespace AvatarLauncher;

internal sealed class Options
{
	public string Python { get; set; } = "";
	public string Script { get; set; } = "";
	public string WorkingDirectory { get; set; } = "";
	public bool RestartOnFailure { get; set; } = true;
	public int MaxRestarts { get; set; } = 3;
	public double RestartDelaySeconds { get; set; } = 2;
	public string LogPath { get; set; } = "";

	public const string FileName = "launcher.json";

	public string? ConfigProblem { get; private set; }

	public static Options Load(string baseDirectory)
	{
		var path = Path.Combine(baseDirectory, FileName);
		var options = ReadFile(path, out var problem) ?? new Options();
		options.ConfigProblem = problem;
		var root = FindRoot(baseDirectory);

		if (options.Python.Length == 0 && root is not null)
			options.Python = Path.Combine(root, ".venv", "Scripts", "pythonw.exe");
		if (options.Script.Length == 0 && root is not null)
			options.Script = Path.Combine(root, "experiments", "host.py");
		if (options.WorkingDirectory.Length == 0)
			options.WorkingDirectory = root ?? baseDirectory;
		if (options.LogPath.Length == 0)
			options.LogPath = Path.Combine(
				Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
				"avatar_project", "launcher.log");

		return options;
	}

	public string? Validate(bool requireScript)
	{
		if (Python.Length == 0 || !File.Exists(Python))
			return $"python not found: {(Python.Length == 0 ? "<undiscovered>" : Python)}";
		if (requireScript && (Script.Length == 0 || !File.Exists(Script)))
			return $"entry script not found: {(Script.Length == 0 ? "<undiscovered>" : Script)}";
		return null;
	}

	private static Options? ReadFile(string path, out string? problem)
	{
		problem = null;
		if (!File.Exists(path))
			return null;
		try
		{
			return JsonSerializer.Deserialize<Options>(File.ReadAllText(path), new JsonSerializerOptions
			{
				PropertyNameCaseInsensitive = true,
				ReadCommentHandling = JsonCommentHandling.Skip,
			});
		}
		catch (Exception ex)
		{
			problem = $"{FileName} ignored: {ex.Message}";
			return null;
		}
	}

	private static string? FindRoot(string start)
	{
		var directory = new DirectoryInfo(start);
		while (directory is not null)
		{
			if (File.Exists(Path.Combine(directory.FullName, ".venv", "Scripts", "pythonw.exe")))
				return directory.FullName;
			directory = directory.Parent;
		}
		return null;
	}
}
