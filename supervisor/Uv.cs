using System.Diagnostics;
using System.IO.Compression;

namespace Supervisor;

internal sealed class UvResult
{
	public int Code;
	public List<string> Output = new();

	public bool Ok => Code == 0;
	public string Text => string.Join(Environment.NewLine, Output);
}

/// <summary>Everything that touches python goes through uv. The only network code here fetches uv itself.</summary>
internal sealed class Uv
{
	private readonly Plan __plan;
	private readonly Log __log;

	public Uv(Plan plan, Log log)
	{
		__plan = plan;
		__log = log;
	}

	public bool Ensure(Action<string> progress)
	{
		if (File.Exists(__plan.UvExe))
			return true;

		Directory.CreateDirectory(__plan.Workspace);
		var archive = Path.Combine(__plan.Workspace, "uv.zip");

		if (!Download(__plan.UvSource.Url, archive, progress))
			return false;

		progress("Unpacking uv");
		try
		{
			if (Directory.Exists(__plan.UvHome))
				Directory.Delete(__plan.UvHome, true);
			Directory.CreateDirectory(__plan.UvHome);
			ZipFile.ExtractToDirectory(archive, __plan.UvHome, true);
			File.Delete(archive);
		}
		catch (Exception ex)
		{
			__log.Write("prov", $"unpacking uv failed: {ex.Message}");
			return false;
		}

		if (File.Exists(__plan.UvExe))
			return true;

		// Some archives carry a top level directory; take the first uv.exe under it.
		var found = Directory.GetFiles(__plan.UvHome, "uv.exe", SearchOption.AllDirectories).FirstOrDefault();
		if (found is null)
		{
			__log.Write("prov", "uv.exe is not in the archive");
			return false;
		}

		File.Copy(found, __plan.UvExe, true);
		return true;
	}

	public UvResult InstallPython() =>
		Run("python", "install", __plan.PythonVersion, "--install-dir", __plan.PythonHome);

	public UvResult CreateVenv() =>
		Run("venv", __plan.VenvDirectory, "--python", __plan.PythonVersion);

	public UvResult Install(IEnumerable<string> requirements, bool dryRun)
	{
		var arguments = new List<string> { "pip", "install", "--python", __plan.VenvConsolePython };
		if (dryRun)
			arguments.Add("--dry-run");
		if (__plan.Index.Length > 0)
		{
			arguments.Add("--index-url");
			arguments.Add(__plan.Index);
		}
		arguments.AddRange(requirements);
		return Run(arguments.ToArray());
	}

	public HashSet<string> Installed()
	{
		var names = new HashSet<string>();
		var result = Run("pip", "freeze", "--python", __plan.VenvConsolePython);
		if (!result.Ok)
			return names;

		foreach (var line in result.Output)
		{
			var text = line.Trim();
			if (text.Length == 0 || text.StartsWith('#') || text.StartsWith('-'))
				continue;
			names.Add(Requirements.Name(text));
		}
		return names;
	}

	/// <summary>
	/// Distributions a dry run says it would add, change or remove. An empty set with a
	/// failed parse is never reported as "nothing changes" — the caller gets null and defers.
	/// </summary>
	public HashSet<string>? WouldTouch(IEnumerable<string> requirements)
	{
		var result = Install(requirements, true);
		if (!result.Ok)
			return null;

		var touched = new HashSet<string>();
		var sawPlan = false;
		foreach (var line in result.Output)
		{
			var text = line.Trim();
			if (text.StartsWith("Would ", StringComparison.OrdinalIgnoreCase))
				sawPlan = true;
			if (text.Length < 3 || (text[0] != '+' && text[0] != '-' && text[0] != '~'))
				continue;
			touched.Add(Requirements.Name(text[1..].Trim()));
		}

		if (touched.Count > 0)
			return touched;
		if (sawPlan)
			return null; // it plans to do something it did not itemise; be conservative
		return touched;
	}

	public UvResult Run(params string[] arguments)
	{
		var info = new ProcessStartInfo(__plan.UvExe)
		{
			WorkingDirectory = __plan.Workspace,
			UseShellExecute = false,
			CreateNoWindow = true,
			RedirectStandardOutput = true,
			RedirectStandardError = true,
		};
		foreach (var argument in arguments)
			info.ArgumentList.Add(argument);

		info.Environment["UV_PYTHON_INSTALL_DIR"] = __plan.PythonHome;
		info.Environment["UV_CACHE_DIR"] = Path.Combine(__plan.Workspace, "cache");
		info.Environment["UV_NO_PROGRESS"] = "1";

		var result = new UvResult();
		using var process = new Process { StartInfo = info };
		process.OutputDataReceived += (_, args) => Capture(result, args.Data);
		process.ErrorDataReceived += (_, args) => Capture(result, args.Data);

		try
		{
			process.Start();
		}
		catch (Exception ex)
		{
			__log.Write("prov", $"cannot run uv: {ex.Message}");
			result.Code = -1;
			return result;
		}

		process.BeginOutputReadLine();
		process.BeginErrorReadLine();
		process.WaitForExit();
		result.Code = process.ExitCode;
		return result;
	}

	private void Capture(UvResult result, string? line)
	{
		if (line is null)
			return;
		lock (result.Output)
			result.Output.Add(line);
		__log.Write("prov", line);
	}

	private bool Download(string url, string target, Action<string> progress)
	{
		progress("Downloading uv");
		__log.Write("prov", $"downloading {url}");
		try
		{
			using var client = new HttpClient { Timeout = TimeSpan.FromMinutes(15) };
			using var response = client.Send(new HttpRequestMessage(HttpMethod.Get, url), HttpCompletionOption.ResponseHeadersRead);
			response.EnsureSuccessStatusCode();

			var total = response.Content.Headers.ContentLength ?? 0;
			using var source = response.Content.ReadAsStream();
			using var file = File.Create(target);

			var buffer = new byte[81920];
			long done = 0;
			var reported = -1;
			int read;
			while ((read = source.Read(buffer, 0, buffer.Length)) > 0)
			{
				file.Write(buffer, 0, read);
				done += read;
				if (total <= 0)
					continue;
				var percent = (int)(done * 100 / total);
				if (percent == reported)
					continue;
				reported = percent;
				progress($"Downloading uv {percent}%");
			}
			return true;
		}
		catch (Exception ex)
		{
			__log.Write("prov", $"download failed: {ex.Message}");
			return false;
		}
	}
}
