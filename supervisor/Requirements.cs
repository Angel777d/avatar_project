using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;

namespace Supervisor;

internal static partial class Requirements
{
	private const string Host = "github.com";

	[GeneratedRegex(@"^[A-Za-z0-9]([A-Za-z0-9._-]*[A-Za-z0-9])?$")]
	private static partial Regex NamePattern();

	[GeneratedRegex(@"^\[[A-Za-z0-9,._-]+\]$")]
	private static partial Regex ExtrasPattern();

	[GeneratedRegex(@"^((==|!=|<=|>=|<|>|~=|===)\s*[A-Za-z0-9*+!._-]+)(\s*,\s*((==|!=|<=|>=|<|>|~=|===)\s*[A-Za-z0-9*+!._-]+))*$")]
	private static partial Regex SpecifierPattern();

	/// <summary>Null when the requirement is one the supervisor is willing to hand to uv.</summary>
	public static string? Validate(string requirement)
	{
		if (string.IsNullOrWhiteSpace(requirement))
			return "empty requirement";
		if (requirement.IndexOfAny(new[] { '\r', '\n' }) >= 0)
			return "requirement contains a line break";
		if (requirement.TrimStart().StartsWith('-'))
			return "requirement starts with a dash, which is an option and not a package";

		var text = requirement.Trim();
		var mark = FindDirectMark(text);
		return mark < 0 ? ValidateNamed(text) : ValidateDirect(text[..mark].Trim(), text[(mark + 1)..].Trim());
	}

	public static string Name(string requirement)
	{
		var text = requirement.Trim();
		var mark = FindDirectMark(text);
		if (mark >= 0)
			text = text[..mark];

		var cut = text.IndexOfAny(new[] { '[', '<', '>', '=', '!', '~', ';', ' ' });
		if (cut >= 0)
			text = text[..cut];

		return Normalize(text);
	}

	public static string Normalize(string name)
	{
		var builder = new StringBuilder(name.Length);
		foreach (var symbol in name.Trim().ToLowerInvariant())
			builder.Append(symbol is '_' or '.' ? '-' : symbol);
		return builder.ToString();
	}

	public static string Fingerprint(string index, IEnumerable<string> set, int revision)
	{
		var material = new StringBuilder();
		material.Append(index).Append('\n').Append(revision).Append('\n');
		foreach (var entry in set.OrderBy(entry => entry, StringComparer.Ordinal))
			material.Append(entry).Append('\n');
		return Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(material.ToString()))).ToLowerInvariant();
	}

	public static string Fingerprint(params string[] parts) =>
		Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(string.Join('\n', parts)))).ToLowerInvariant();

	private static int FindDirectMark(string text)
	{
		// The '@' of a PEP 508 direct reference, not one inside a git ref or a url.
		var mark = text.IndexOf('@');
		while (mark > 0)
		{
			var before = text[mark - 1];
			var after = mark + 1 < text.Length ? text[mark + 1] : '\0';
			if (char.IsWhiteSpace(before) || char.IsWhiteSpace(after))
				return mark;
			mark = text.IndexOf('@', mark + 1);
		}
		return -1;
	}

	private static string? ValidateNamed(string text)
	{
		var name = text;
		var extras = "";
		var specifier = "";

		var open = name.IndexOf('[');
		if (open >= 0)
		{
			var close = name.IndexOf(']', open);
			if (close < 0)
				return $"malformed extras in \"{text}\"";
			extras = name[open..(close + 1)];
			name = name[..open] + name[(close + 1)..];
		}

		var cut = name.IndexOfAny(new[] { '<', '>', '=', '!', '~' });
		if (cut >= 0)
		{
			specifier = name[cut..].Trim();
			name = name[..cut];
		}

		name = name.Trim();
		if (!NamePattern().IsMatch(name))
			return $"\"{text}\" is not a package name";
		if (extras.Length > 0 && !ExtrasPattern().IsMatch(extras))
			return $"malformed extras in \"{text}\"";
		if (specifier.Length > 0 && !SpecifierPattern().IsMatch(specifier))
			return $"malformed version specifier in \"{text}\"";
		return null;
	}

	private static string? ValidateDirect(string left, string url)
	{
		if (ValidateNamed(left) is { } problem)
			return problem;

		var target = url;
		if (target.StartsWith("git+", StringComparison.OrdinalIgnoreCase))
			target = target[4..];

		if (!Uri.TryCreate(target, UriKind.Absolute, out var uri))
			return $"\"{url}\" is not a url";
		if (uri.Scheme != Uri.UriSchemeHttps)
			return $"\"{url}\" is not https";
		if (!uri.Host.Equals(Host, StringComparison.OrdinalIgnoreCase))
			return $"\"{uri.Host}\" is not an allowed source, only {Host} and the package index are";
		return null;
	}

	public static bool NeedsGit(string requirement) =>
		requirement.Contains("git+", StringComparison.OrdinalIgnoreCase);
}
