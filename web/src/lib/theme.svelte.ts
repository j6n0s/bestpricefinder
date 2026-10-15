/**
 * The colour theme ("Megjelenés") as Svelte 5 `$state`, persisted through the storage module like the language.
 *
 * `preference` is the user's choice: "system" (the default: the browser's prefers-color-scheme setting), "light"
 * or "dark". `effective` is what is shown. The document carries `data-theme="light|dark"` only for an explicit
 * choice (src/app.css keys its dark tokens on it, and on the media query otherwise), and the theme-color metas
 * follow it, so the browser's own bars match the page. The preference stays on this device (StoredState.theme).
 */
import { isTheme, load, update, type Theme } from './storage';

let preference = $state<Theme>(load().theme);
let systemDark = $state(false);
let watching = false;

/** Follows the browser's setting, for the effective theme while the preference is "system". */
function watchSystem(): void {
	if (watching || typeof matchMedia === 'undefined') return;
	watching = true;
	const query = matchMedia('(prefers-color-scheme: dark)');
	systemDark = query.matches;
	if (typeof query.addEventListener === 'function') {
		query.addEventListener('change', (event) => {
			systemDark = event.matches;
		});
	}
}

/** Reactive read access: `theme.preference`, `theme.effective`. */
export const theme = {
	get preference(): Theme {
		return preference;
	},
	get effective(): 'light' | 'dark' {
		if (preference !== 'system') return preference;
		return systemDark ? 'dark' : 'light';
	}
};

/** The page background per theme (src/app.css --color-bg), for the browser's bars. */
const THEME_COLORS: Readonly<Record<'light' | 'dark', string>> = { light: '#ffffff', dark: '#000000' };

/** Writes the choice to <html data-theme> and the theme-color metas. Safe outside the browser. */
export function syncDocumentTheme(choice: Theme = preference): void {
	if (typeof document === 'undefined') return;
	watchSystem();
	const root = document.documentElement;
	if (choice === 'system') delete root.dataset.theme;
	else root.dataset.theme = choice;
	for (const meta of document.querySelectorAll<HTMLMetaElement>('meta[name="theme-color"]')) {
		// Each meta serves one browser setting (its media attribute); an explicit choice overrides both.
		const own = (meta.getAttribute('media') ?? '').includes('dark') ? 'dark' : 'light';
		meta.content = THEME_COLORS[choice === 'system' ? own : choice];
	}
}

/** Chooses the theme and stores the choice on this device. */
export function setTheme(choice: Theme): void {
	if (!isTheme(choice)) return;
	preference = choice;
	update({ theme: choice });
	syncDocumentTheme(choice);
}

/** The header's switch: the opposite of what is shown now, as an explicit choice. */
export function toggleTheme(): void {
	setTheme(theme.effective === 'dark' ? 'light' : 'dark');
}

/** Re-reads the stored choice (after "minden adat törlése" it follows the browser again). */
export function reloadTheme(): void {
	preference = load().theme;
	syncDocumentTheme(preference);
}
