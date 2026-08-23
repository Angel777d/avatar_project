namespace Supervisor;

internal sealed class Log
{
	private const long MaxBytes = 1_000_000;
	private const int Generations = 3;

	private readonly string __path;
	private readonly object __gate = new();

	public Log(string path)
	{
		__path = path;
		Directory.CreateDirectory(Path.GetDirectoryName(path)!);
		Rotate();
	}

	public void Write(string line) => Write("sup", line);

	public void Write(string source, string line)
	{
		lock (__gate)
		{
			try
			{
				File.AppendAllText(__path, $"{DateTime.Now:yyyy-MM-dd HH:mm:ss} {source,-5}| {line}{Environment.NewLine}");
			}
			catch (IOException)
			{
			}
		}
	}

	private void Rotate()
	{
		try
		{
			var file = new FileInfo(__path);
			if (!file.Exists || file.Length < MaxBytes)
				return;

			var oldest = $"{__path}.{Generations}";
			if (File.Exists(oldest))
				File.Delete(oldest);

			for (var index = Generations - 1; index >= 1; index--)
			{
				var from = $"{__path}.{index}";
				if (File.Exists(from))
					File.Move(from, $"{__path}.{index + 1}");
			}

			File.Move(__path, $"{__path}.1");
		}
		catch (IOException)
		{
		}
	}
}
