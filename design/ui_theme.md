# UI theme — design

Every page is a standalone HTML document, and every one of them carries its own copy of the design. One stylesheet, delivered through the mechanism that already delivers `editor.css`, replaces all of it.

## What the pages actually contain

Five pages, 2002 lines: 796 of CSS, 990 of script, 216 of markup. The CSS is 40% of the total and most of it is not about the page.

**Eight tokens are declared byte-identically in all five** — `--bg`, `--panel`, `--panel-edge`, `--card`, `--card-edge`, `--text`, `--muted`, `--accent` — along with `* { box-sizing: border-box }` and the same `"Segoe UI", system-ui, sans-serif` stack. Nothing is gained by any page owning them.

**The drift has already started**, in exactly the place the shared eight ran out:

| token | one page says | another says |
| --- | --- | --- |
| `--bad` | `#e06c75` | `#e2686d` |
| `--warn` | `#d8a657` | `#e0a458` |
| green | `--ok: #57b98a` | `--rest: #57b98a` |

The last row is the one to learn from: the same colour under two names, because there was nowhere to agree on one. Two pages needed a semantic colour, invented it locally, and produced three inconsistencies between them.

**A sixth copy lives in `editor.css`**, which writes `var(--panel, #1e2127)` — a variable *and* a hardcoded fallback, because a shared asset cannot assume the page defines a theme. Once one does, the fallbacks go.

**The component vocabulary is converging without being shared.** `.tag` appears in three pages, `.empty` in three, `.card` in two, a bare `button` base in two — each written separately, each slightly different. The agreement on names is evidence the vocabulary is real; the differences are the cost of having no place to put it.

## The theme

One file, `assets/theme.css`, in three layers.

**Tokens.** The eight, plus the semantic colours resolved to one value each, plus the few metrics every page re-picks by eye.

```css
:root {
	--bg: #16181d;  --panel: #1e2127;  --panel-edge: #2b2f38;
	--card: #262a33;  --card-edge: #343945;
	--text: #e6e8ec;  --muted: #8b93a3;
	--accent: #4e96e6;  --on-accent: #0d1117;
	--ok: #57b98a;  --warn: #e0a458;  --bad: #e2686d;
	--radius: 8px;  --radius-small: 6px;
	--font: 14px "Segoe UI", system-ui, sans-serif;
}
```

Where two values existed the incumbent wins, not the newest: `--warn` and `--bad` take the statistics page's values, and the green settles on `--ok` since `--rest` named a pomodoro phase rather than a colour. **A token is named for what it means, never for where it was first needed** — that is what stops the next page inventing `--pause` for the same green.

**Elements.** The reset, the body defaults, and bare `button`, `input`, `textarea`, `select`, `h2`. Styling bare elements rather than classes means existing markup is themed without being touched, and a page that writes `<button>Apply</button>` gets the right thing by default.

**Components.** Only what the pages have already independently invented, promoted to one definition:

| class | what it is |
| --- | --- |
| `.card` | the `--card` surface with its edge — a kanban card, a list row |
| `.panel` | the `--panel` surface with its edge — a statistics tile, a section |
| `.tag` | a pill label, with `.ok` `.warn` `.bad` `.accent` tones |
| `.empty` | the muted line standing in for an empty list |
| `button.primary`, `button.link` | the two variants that already exist twice each |

Nothing is invented here that no page has asked for. A component earns its place by appearing twice — which is why `.bar`, `.row` and `.scroll` are not in this table after all: one page had a `.row`, none had the others.

**`.card` was a collision.** Kanban's `.card` paints `--card`; the statistics page's `.card` painted `--panel`. Same name, two surfaces, and no single definition could serve both. The rule that resolves it is that **a surface class is named for the token it paints**, so kanban keeps `.card` and the statistics tiles become `.panel`.

## Delivery

`page.py` injects the theme on its own rather than through `SHARED`, because two things about *how* differ.

**It must arrive before the page's own styles.** `SHARED` is injected after `loadFinished`, appending to `<head>`, so a shared rule would land *after* the page's `<style>` and win ties it should lose — a base layer must be overridable by the page that uses it. Registering the theme as a `QWebEngineScript` at `DocumentCreation` puts it in the document before the page's own style element is parsed, which is both the correct cascade order and the fix for the second problem.

**At DocumentCreation the document is empty** — not just `document.head` but `document.documentElement` is null, so a script that reaches for either finds nothing and silently does nothing. The theme script waits with a `MutationObserver` and inserts the moment `head` exists, which is still before the page's own `<style>` is parsed. Without that wait the injection appears to be registered and simply never happens.

**The flash goes away.** Injecting after load means the page renders unstyled for a frame first. At `DocumentCreation` there is nothing to flash.

`editor.css` drops its fallbacks in the same pass; the theme it was hedging against is now guaranteed.

## What a page keeps

Its own layout, and nothing else. The kanban columns, the calendar grid, the pomodoro dial, the statistics charts — the parts that are genuinely that page's. A page declaring a colour is a signal that either the token is missing from the theme or the page is wrong.

Migration is subtraction: delete the `:root` block, the reset, the body font and background, and any `button`, `.tag`, `.card` or `.empty` rules the theme now provides. Around 40 to 60 lines leave each page and nothing is added.

## Out of scope

The script half. The QWebChannel handshake, `snapshot()` and the re-render cycle are repeated in all five pages too, but they are the page-to-python contract and a separate design.
