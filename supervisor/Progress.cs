using System.Windows.Forms;

namespace AvatarLauncher;

internal sealed class ProgressWindow : Form
{
	private readonly Label __label = new();
	private readonly ProgressBar __bar = new();

	public ProgressWindow()
	{
		Text = "Avatar";
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
