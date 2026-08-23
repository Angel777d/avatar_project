using System.Windows.Forms;

namespace Supervisor;

internal interface IReporter
{
	void Step(string message);
	void Fail(string message);
	void Run(Task work);
}

internal sealed class SilentReporter : IReporter
{
	public void Step(string message)
	{
	}

	public void Fail(string message)
	{
	}

	public void Run(Task work) => work.Wait();
}

internal sealed class ConsoleReporter : IReporter
{
	public void Step(string message) => Console.WriteLine(message);

	public void Fail(string message) => Console.Error.WriteLine(message);

	public void Run(Task work) => work.Wait();
}

internal sealed class WindowReporter : IReporter, IDisposable
{
	private readonly string __title;
	private ProgressWindow? __window;

	public WindowReporter(string title) => __title = title;

	public void Step(string message) => __window?.Report(message);

	public void Fail(string message)
	{
		__window?.Report(message);
		MessageBox.Show(message, __title, MessageBoxButtons.OK, MessageBoxIcon.Error);
	}

	public void Run(Task work)
	{
		__window = new ProgressWindow(__title);
		__window.RunUntil(work);
		__window.Dispose();
		__window = null;
	}

	public void Dispose() => __window?.Dispose();
}

internal sealed class ProgressWindow : Form
{
	private readonly Label __label = new();
	private readonly ProgressBar __bar = new();

	public ProgressWindow(string title)
	{
		Text = title;
		FormBorderStyle = FormBorderStyle.FixedDialog;
		StartPosition = FormStartPosition.CenterScreen;
		MaximizeBox = false;
		MinimizeBox = false;
		ControlBox = false;
		ClientSize = new System.Drawing.Size(360, 96);

		__label.SetBounds(18, 20, 324, 20);
		__label.Text = "Getting ready";

		__bar.SetBounds(18, 48, 324, 16);
		__bar.Style = ProgressBarStyle.Marquee;
		__bar.MarqueeAnimationSpeed = 30;

		Controls.Add(__label);
		Controls.Add(__bar);
	}

	public void Report(string message)
	{
		if (IsDisposed || !IsHandleCreated)
			return;
		try
		{
			BeginInvoke(() =>
			{
				__label.Text = message;
				var percent = Percent(message);
				if (percent < 0)
					return;
				__bar.Style = ProgressBarStyle.Continuous;
				__bar.Value = Math.Clamp(percent, 0, 100);
			});
		}
		catch (InvalidOperationException)
		{
		}
	}

	public void RunUntil(Task task)
	{
		var timer = new System.Windows.Forms.Timer { Interval = 100 };
		timer.Tick += (_, _) =>
		{
			if (!task.IsCompleted)
				return;
			timer.Stop();
			Close();
		};
		timer.Start();
		Application.Run(this);
	}

	private static int Percent(string message)
	{
		var mark = message.IndexOf('%');
		if (mark <= 0)
			return -1;
		var start = mark - 1;
		while (start > 0 && char.IsDigit(message[start - 1]))
			start--;
		return int.TryParse(message.AsSpan(start, mark - start), out var value) ? value : -1;
	}
}
