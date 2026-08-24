(() => {
	let Real = null;

	const wrap = (object) => {
		const pending = [];
		let last = null;

		object.changed.connect(() => {
			if (!pending.length) return;
			const waiting = pending.splice(0, pending.length);
			object.state((data) => waiting.forEach((resolve) => resolve(data)));
		});

		const call = (name, args) => {
			const resolve = typeof args[args.length - 1] === "function" ? args.pop() : null;
			if (!resolve) {
				object.invoke(name, JSON.stringify(args));
				return;
			}

			// A page asks for its state on every change. Answering an unchanged question from
			// the cache is what stops changed -> ask -> push -> changed from running forever.
			const key = name + ":" + JSON.stringify(args);
			if (args.length === 0 || key === last) {
				object.state(resolve);
				return;
			}

			last = key;
			pending.push(resolve);
			object.invoke(name, JSON.stringify(args));
		};

		return new Proxy(object, {
			get(target, name) {
				if (typeof name !== "string") return target[name];
				if (name === "changed" || name === "state") return target[name];
				if (name in target && name !== "snapshot") return target[name];
				return (...args) => call(name, args);
			},
		});
	};

	const Wrapped = function (transport, callback) {
		return new Real(transport, (channel) => {
			for (const name of Object.keys(channel.objects))
				channel.objects[name] = wrap(channel.objects[name]);
			callback(channel);
		});
	};

	Object.defineProperty(window, "QWebChannel", {
		configurable: true,
		get() { return Real ? Wrapped : undefined; },
		set(value) { Real = value; },
	});
})();
