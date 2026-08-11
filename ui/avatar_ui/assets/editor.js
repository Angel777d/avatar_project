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

	const tagBox = document.createElement("div");
	tagBox.className = "tags";
	const chips = document.createElement("div");
	chips.className = "chips";
	const tagInput = document.createElement("input");
	tagInput.className = "tag-input";
	tagInput.placeholder = "add a tag…";
	tagInput.setAttribute("list", "avatar-editor-tags");
	const known = document.createElement("datalist");
	known.id = "avatar-editor-tags";
	tagBox.append(chips, tagInput, known);

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

	sheet.append(title, text, tagBox, extra, foot);
	root.appendChild(sheet);

	let current = null;
	let fields = {};
	let chosen = [];
	let palette = [];

	function renderChips() {
		chips.textContent = "";
		chosen.forEach((name) => {
			const chip = document.createElement("span");
			chip.className = "chip";
			const tag = palette.find((item) => item.name === name);
			if (tag && tag.color) {
				chip.style.borderColor = tag.color;
				chip.style.color = tag.color;
			}
			chip.textContent = name;

			const drop = document.createElement("button");
			drop.textContent = "×";
			drop.addEventListener("click", () => {
				chosen = chosen.filter((taken) => taken !== name);
				renderChips();
			});

			chip.appendChild(drop);
			chips.appendChild(chip);
		});
	}

	function addTag(raw) {
		const name = (raw || "").trim();
		if (!name || chosen.includes(name)) return;
		chosen.push(name);
		renderChips();
	}

	function close() {
		current = null;
		fields = {};
		chosen = [];
		palette = [];
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
		const tags = chosen.slice();
		close();
		if (value && done) done({title: value, text: body, values: values, tags: tags, was: named});
	}

	function open(options) {
		current = options || {};
		title.value = current.title || "";
		text.value = current.text || "";
		stamp.textContent = current.stamp || "";
		extra.textContent = "";
		fields = {};

		tagBox.hidden = !current.tags;
		chosen = current.tags ? (current.tags.selected || []).slice() : [];
		palette = current.tags ? (current.tags.all || []) : [];
		known.textContent = "";
		palette.forEach((tag) => {
			const option = document.createElement("option");
			option.value = tag.name;
			known.appendChild(option);
		});
		tagInput.value = "";
		renderChips();

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

	tagInput.addEventListener("keydown", (event) => {
		if (event.key !== "Enter") return;
		event.preventDefault();
		addTag(tagInput.value);
		tagInput.value = "";
	});

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
		addTag: addTag,
		tags: () => chosen.slice(),
		element: root,
	};
})();
