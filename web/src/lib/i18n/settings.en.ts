import type { settingsHu } from './settings.hu';
import type { Messages } from './types';

export const settingsEn: Messages<typeof settingsHu> = {
	title: 'Settings',
	storage_unavailable:
		'The browser does not allow saving data (for example in private mode). Your settings last only until you close this tab.',

	household_title: 'Household',
	people_label: 'How many people do you plan for?',
	people_decrease: 'One person fewer',
	people_increase: 'One person more',
	people_value_one: '{count}\u00a0person',
	people_value_other: '{count}\u00a0people',
	slots_label: 'Meals per day',
	slots_3: '3 meals: breakfast, lunch, dinner',
	slots_5: '5 meals: breakfast, morning snack, lunch, afternoon snack, dinner',

	stores_title: 'Store search',
	radius_label: 'Search radius',
	radius_hint: '{min}–{max} km',

	language_title: 'Language',
	language_hu: 'Magyar',
	language_en: 'English',
	theme_title: 'Appearance',
	theme_system: 'Follow the system',
	theme_light: 'Light',
	theme_dark: 'Dark',

	location_title: 'Location and district',
	location_status_label: 'Location',
	location_status_unset: 'Not allowed.',
	location_status_granted: 'Allowed. Approximate location taken at {time}.',
	location_status_declined: 'Declined.',
	location_revoke: 'Revoke permission',
	location_revoked: 'The stored location has been deleted. You can also revoke the permission in the browser settings.',
	location_source_label: 'Starting point:',
	location_source_none: 'not set yet.',
	location_source_device: 'your device’s approximate location.',
	location_use_district: 'Use the district',
	location_source_map: 'the point chosen on the map.',
	location_use_map: 'Use the map point',

	pantry_title: 'Pantry',
	exclusions_title: 'Excluded ingredients and tags',

	clear_title: 'Delete data',
	clear_button: 'Delete all data',
	clear_confirm_title: 'Delete all data?',
	clear_confirm_text: 'This cannot be undone.',
	clear_confirm_yes: 'Yes, delete everything',
	clear_confirm_no: 'Cancel',
	clear_done: 'All data deleted.',
	clear_partial:
		'All data is cleared from this session, but the browser did not allow access to its storage. If it saved data earlier, you can delete it in the browser settings (site data).'
};
