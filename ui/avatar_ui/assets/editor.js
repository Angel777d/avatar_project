(() => {
	if (window.avatarEditor) return;

	const root = document.createElement("div");
	root.className = "avatar-editor";
	root.hidden = true;

	const sheet = document.createElement("div");
	sheet.className = "sheet";

	const title = document.createElement("input");
	title.className = "editor-title";
	title.placeholder = "Title";

	const text = document.createElement("textarea");
	text.className = "editor-text";
	text.placeholder = "Description…";

	const extra = document.createElement("div");
	extra.className = "extra";

	const foot = document.createElement("div");
	foot.className = "foot";
	const stamp = document.createElement("span");
	stamp.className = "editor-stamp";
	const cancel = document.createElement("button");
	cancel.className = "cancel";
	cancel.textContent = "Cancel";
	const save = document.createElement("button");
	save.className = "save";
	save.textContent = "Save";
	foot.append(stamp, cancel, save);

	sheet.append(title, text, extra, foot);
	root.appendChild(sheet);

	let current = null;
	let fields = {};

	function close() {
		current = null;
		fields = {};
		root.hidden = true;
	}

	function commit() {
		if (!current) return;
		const named = current.title;
		const value = title.value.trim();
		const done = current.onSave;
		const values = {};
		Object.keys(fields).forEach((name) => { values[name] = fields[name].value; });
		const body = text.value;
		close();
		if (value && done) done({title: value, text: body, values: values, was: named});
	}

	function open(options) {
		current = options || {};
		title.value = current.title || "";
		text.value = current.text || "";
		stamp.textContent = current.stamp || "";
		extra.textContent = "";
		fields = {};

		(current.fields || []).forEach((field) => {
			const label = document.createElement("label");
			label.textContent = field.label || field.name;
			const input = document.createElement("input");
			input.type = field.type || "text";
			input.value = field.value || "";
			if (field.placeholder) input.placeholder = field.placeholder;
			label.appendChild(input);
			extra.appendChild(label);
			fields[field.name] = input;
		});

		root.hidden = false;
		title.focus();
		title.select();
	}

	save.addEventListener("click", commit);
	cancel.addEventListener("click", close);
	root.addEventListener("click", (event) => {
		if (event.target === root) close();
	});
	document.addEventListener("keydown", (event) => {
		if (root.hidden) return;
		if (event.key === "Escape") close();
		else if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) commit();
	});

	const attach = () => document.body.appendChild(root);
	if (document.body) attach();
	else document.addEventListener("DOMContentLoaded", attach);

	window.avatarEditor = {
		open: open,
		close: close,
		isOpen: () => !root.hidden,
		element: root,
	};
})();
