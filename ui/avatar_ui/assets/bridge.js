(() => {
	let Real = null;

	const wrap = (object) => {
		const call = (name, args) => {
			const resolve = typeof args[args.length - 1] === "function" ? args.pop() : null;
			if (resolve) {
				object.state(resolve);
				return;
			}
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
