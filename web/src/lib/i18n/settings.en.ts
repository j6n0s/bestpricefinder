import type { settingsHu } from './settings.hu';
import type { Messages } from './types';

export const settingsEn: Messages<typeof settingsHu> = {
	title: 'Settings',
	intro: 'These settings are stored on this device only.',
	storage_unavailable:
		'The browser does not allow saving data (for example in private mode). Your settings last only until you close this tab.',

	household_title: 'Household',
	people_label: 'How many people do you plan for?',
	people_decrease: 'One person fewer',
	people_increase: 'One person more',
	people_value_one: '{count} person',
	people_value_other: '{count} people',
	slots_label: 'Meals per day',
	slots_3: '3 meals: breakfast, lunch, dinner',
	slots_5: '5 meals: breakfast, morning snack, lunch, afternoon snack, dinner',

	stores_title: 'Store search',
	radius_label: 'Search radius',
	radius_hint: 'Stores are searched within this distance ({min}–{max} km).',

	language_title: 'Language',
	language_hu: 'Magyar',
	language_en: 'English',

	location_title: 'Location and district',
	location_status_label: 'Location',
	location_status_unset: 'Not allowed.',
	location_status_granted: 'Allowed. Approximate location taken at {time}.',
	location_status_declined: 'Declined. You can choose a district at any time.',
	location_revoke: 'Revoke permission',
	location_revoked: 'The stored location has been deleted. You can also revoke the permission in the browser settings.',
	location_source_label: 'Distances are measured from:',
	location_source_none: 'not set yet.',
	location_source_device: 'your device’s approximate location.',
	location_use_district: 'Use the district',

	pantry_title: 'Pantry',
	exclusions_title: 'Excluded ingredients and tags',

	clear_title: 'Delete data',
	clear_description:
		'Deletes all data stored on this device: the plan, the cart, the settings, the pantry, the exclusions, the location and the list ticks.',
	clear_button: 'Delete all data',
	clear_confirm_title: 'Delete all data?',
	clear_confirm_text: 'This cannot be undone.',
	clear_confirm_yes: 'Yes, delete everything',
	clear_confirm_no: 'Cancel',
	clear_done: 'All data deleted.',
	clear_partial:
		'All data is cleared from this session, but the browser did not allow access to its storage. If it saved data earlier, you can delete it in the browser settings (site data).'
};
