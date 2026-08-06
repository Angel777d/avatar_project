using System.Diagnostics;
using System.Security.Cryptography;
using System.Text.Json;

namespace AvatarLauncher;

internal sealed class PythonSource
{
	public string Url { get; set; } = "";
	public string Sha256 { get; set; } = "";
	public string Home { get; set; } = "python";
}

internal sealed class EntryPoint
{
	public string Module { get; set; } = "";
	public string Script { get; set; } = "";
}

internal sealed class Bootstrap
{
	public const string FileName = "bootstrap.json";

	public string Runtime { get; set; } = @"%LOCALAPPDATA%\avatar_project\runtime";
	public PythonSource Python { get; set; } = new();
	public string Index { get; set; } = "";
	public List<string> Packages { get; set; } = new();
	public EntryPoint Entry { get; set; } = new();

	public string Directory => Environment.ExpandEnvironmentVariables(Runtime);
	public string PythonHome => Path.Combine(Directory, Python.Home);
	public string VenvDirectory => Path.Combine(Directory, ".venv");
	public string VenvPython => Path.Combine(VenvDirectory, "Scripts", "pythonw.exe");
	public string VenvConsolePython => Path.Combine(VenvDirectory, "Scripts", "python.exe");

	private string StateFile => Path.Combine(Directory, "state.json");

	public static Bootstrap? Load(string path, out string? problem)
	{
		problem = null;
		if (!File.Exists(path))
			return null;
		try
		{
			return JsonSerializer.Deserialize<Bootstrap>(File.ReadAllText(path), new JsonSerializerOptions
			{
				PropertyNameCaseInsensitive = true,
				ReadCommentHandling = JsonCommentHandling.Skip,
			});
		}
		catch (Exception ex)
		{
			problem = $"{FileName} is not readable: {ex.Message}";
			return null;
		}
	}

	public List<string> EntryArguments()
	{
		if (Entry.Module.Length > 0)
			return new List<string> { "-m", Entry.Module };
		if (Entry.Script.Length > 0)
			return new List<string> { Environment.ExpandEnvironmentVariables(Entry.Script) };
		return new List<string>();
	}

	public bool IsReady()
	{
		if (!File.Exists(VenvPython) || !File.Exists(StateFile))
			return false;
		try
		{
			return File.ReadAllText(StateFile).Trim() == Fingerprint();
		}
		catch (IOException)
		{
			return false;
		}
	}

	public bool Ensure(Log log, Action<string> progress)
	{
		if (IsReady())
		{
			log.Write("runtime is ready");
			return true;
		}

		System.IO.Directory.CreateDirectory(Directory);

		if (!File.Exists(Path.Combine(PythonHome, "python.exe")))
		{
			if (Python.Sha256.Trim().Length == 0)
			{
				log.Write("no checksum configured, refusing to download python");
				return false;
			}

			var archive = Path.Combine(Directory, "python.tar.gz");
			if (!Download(Python.Url, archive, log, progress))
				return false;
			if (!Verify(archive, Python.Sha256, log, progress))
				return false;
			if (!Extract(archive, Directory, log, progress))
				return false;
			File.Delete(archive);
		}

		if (!File.Exists(VenvConsolePython))
		{
			progress("Preparing the environment");
			log.Write("creating the virtual environment");
			if (Run(Path.Combine(PythonHome, "python.exe"), new[] { "-m", "venv", VenvDirectory }, log) != 0)
			{
				log.Write("could not create the virtual environment");
				return false;
			}
		}

		if (!Install(log, progress))
			return false;

		File.WriteAllText(StateFile, Fingerprint());
		progress("Ready");
		return true;
	}

	private bool Install(Log log, Action<string> progress)
	{
		if (Packages.Count == 0)
			return true;

		progress($"Installing {Packages.Count} packages");
		log.Write($"installing: {string.Join(" ", Packages)}");

		var arguments = new List<string> { "-m", "pip", "install", "--upgrade", "--disable-pip-version-check" };
		if (Index.Length > 0)
		{
			arguments.Add("--index-url");
			arguments.Add(Index);
		}
		arguments.AddRange(Packages);

		if (Run(VenvConsolePython, arguments, log) != 0)
		{
			log.Write("package installation failed");
			return false;
		}
		return true;
	}

	private static bool Download(string url, string target, Log log, Action<string> progress)
	{
		if (url.Length == 0)
		{
			log.Write("no python url configured");
			return false;
		}

		progress("Downloading Python");
		log.Write($"downloading {url}");
		try
		{
			using var client = new HttpClient { Timeout = TimeSpan.FromMinutes(30) };
			using var response = client.Send(new HttpRequestMessage(HttpMethod.Get, url),
				HttpCompletionOption.ResponseHeadersRead);
			response.EnsureSuccessStatusCode();

			var total = response.Content.Headers.ContentLength ?? 0;
			using var source = response.Content.ReadAsStream();
			using var file = File.Create(target);

			var buffer = new byte[81920];
			long done = 0;
			var lastReport = -1;
			int read;
			while ((read = source.Read(buffer, 0, buffer.Length)) > 0)
			{
				file.Write(buffer, 0, read);
				done += read;
				if (total <= 0)
					continue;
				var percent = (int)(done * 100 / total);
				if (percent == lastReport)
					continue;
				lastReport = percent;
				progress($"Downloading Python {percent}%");
			}
			return true;
		}
		catch (Exception ex)
		{
			log.Write($"download failed: {ex.Message}");
			return false;
		}
	}

	private static bool Verify(string archive, string expected, Log log, Action<string> progress)
	{
		if (expected.Length == 0)
		{
			log.Write("no checksum configured, refusing to use the download");
			return false;
		}

		progress("Checking the download");

		string actual;
		using (var stream = File.OpenRead(archive))
			actual = Convert.ToHexString(SHA256.HashData(stream)).ToLowerInvariant();

		if (actual == expected.Trim().ToLowerInvariant())
			return true;

		log.Write($"checksum mismatch: expected {expected}, got {actual}");
		try
		{
			File.Delete(archive);
		}
		catch (IOException ex)
		{
			log.Write($"could not remove the bad download: {ex.Message}");
		}
		return false;
	}

	private static bool Extract(string archive, string target, Log log, Action<string> progress)
	{
		progress("Unpacking Python");
		log.Write("unpacking python");

		var tar = Path.Combine(Environment.SystemDirectory, "tar.exe");
		if (!File.Exists(tar))
		{
			log.Write($"cannot unpack, {tar} is missing");
			return false;
		}

		if (Run(tar, new[] { "-xzf", archive, "-C", target }, log) != 0)
		{
			log.Write("unpacking failed");
			return false;
		}
		return true;
	}

	private static int Run(string exe, IEnumerable<string> arguments, Log log)
	{
		var info = new ProcessStartInfo(exe)
		{
			UseShellExecute = false,
			CreateNoWindow = true,
			RedirectStandardOutput = true,
			RedirectStandardError = true,
		};
		foreach (var argument in arguments)
			info.ArgumentList.Add(argument);

		using var process = new Process { StartInfo = info };
		process.OutputDataReceived += (_, args) =>
		{
			if (args.Data is not null)
				log.Write($"setup | {args.Data}");
		};
		process.ErrorDataReceived += (_, args) =>
		{
			if (args.Data is not null)
				log.Write($"setup | {args.Data}");
		};

		try
		{
			process.Start();
		}
		catch (Exception ex)
		{
			log.Write($"cannot run {exe}: {ex.Message}");
			return -1;
		}

		process.BeginOutputReadLine();
		process.BeginErrorReadLine();
		process.WaitForExit();
		return process.ExitCode;
	}

	private string Fingerprint()
	{
		var material = string.Join("\n", new[] { Python.Url, Python.Sha256, Index }.Concat(Packages));
		return Convert.ToHexString(SHA256.HashData(System.Text.Encoding.UTF8.GetBytes(material))).ToLowerInvariant();
	}
}
