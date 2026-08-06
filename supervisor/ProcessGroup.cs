using System.Diagnostics;
using System.Runtime.InteropServices;

namespace AvatarLauncher;

internal sealed class ProcessGroup : IDisposable
{
	private const int ExtendedLimitInformation = 9;
	private const int LimitKillOnJobClose = 0x2000;

	private IntPtr __handle;

	public ProcessGroup()
	{
		__handle = CreateJobObject(IntPtr.Zero, null);
		if (__handle == IntPtr.Zero)
			return;

		var information = new ExtendedLimit();
		information.Basic.LimitFlags = LimitKillOnJobClose;

		var size = Marshal.SizeOf(information);
		var buffer = Marshal.AllocHGlobal(size);
		try
		{
			Marshal.StructureToPtr(information, buffer, false);
			SetInformationJobObject(__handle, ExtendedLimitInformation, buffer, (uint)size);
		}
		finally
		{
			Marshal.FreeHGlobal(buffer);
		}
	}

	public bool Add(Process process)
	{
		return __handle != IntPtr.Zero && AssignProcessToJobObject(__handle, process.Handle);
	}

	public void Dispose()
	{
		if (__handle == IntPtr.Zero)
			return;
		CloseHandle(__handle);
		__handle = IntPtr.Zero;
	}

	[StructLayout(LayoutKind.Sequential)]
	private struct BasicLimit
	{
		public long PerProcessUserTimeLimit;
		public long PerJobUserTimeLimit;
		public uint LimitFlags;
		public UIntPtr MinimumWorkingSetSize;
		public UIntPtr MaximumWorkingSetSize;
		public uint ActiveProcessLimit;
		public UIntPtr Affinity;
		public uint PriorityClass;
		public uint SchedulingClass;
	}

	[StructLayout(LayoutKind.Sequential)]
	private struct IoCounters
	{
		public ulong ReadOperationCount;
		public ulong WriteOperationCount;
		public ulong OtherOperationCount;
		public ulong ReadTransferCount;
		public ulong WriteTransferCount;
		public ulong OtherTransferCount;
	}

	[StructLayout(LayoutKind.Sequential)]
	private struct ExtendedLimit
	{
		public BasicLimit Basic;
		public IoCounters IoInfo;
		public UIntPtr ProcessMemoryLimit;
		public UIntPtr JobMemoryLimit;
		public UIntPtr PeakProcessMemoryUsed;
		public UIntPtr PeakJobMemoryUsed;
	}

	[DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
	private static extern IntPtr CreateJobObject(IntPtr security, string? name);

	[DllImport("kernel32.dll", SetLastError = true)]
	private static extern bool SetInformationJobObject(IntPtr job, int infoClass, IntPtr info, uint length);

	[DllImport("kernel32.dll", SetLastError = true)]
	private static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);

	[DllImport("kernel32.dll", SetLastError = true)]
	private static extern bool CloseHandle(IntPtr handle);
}
