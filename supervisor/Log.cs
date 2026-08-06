namespace AvatarLauncher;

internal sealed class Log
{
	private readonly string __path;
	private readonly object __gate = new();

	public Log(string path)
	{
		__path = path;
		Directory.CreateDirectory(Path.GetDirectoryName(path)!);
		Trim();
	}

	public void Write(string line)
	{
		lock (__gate)
		{
			try
			{
				File.AppendAllText(__path, $"{DateTime.Now:yyyy-MM-dd HH:mm:ss} {line}{Environment.NewLine}");
			}
			catch (IOException)
			{
			}
		}
	}

	private void Trim()
	{
		try
		{
			var file = new FileInfo(__path);
			if (file.Exists && file.Length > 1_000_000)
				file.Delete();
		}
		catch (IOException)
		{
		}
	}
}
