import type { sourcesHu } from './sources.hu';
import type { Messages } from './types';

export const sourcesEn: Messages<typeof sourcesHu> = {
	title: 'Sources and privacy',

	prices_title: 'Store prices',
	prices_text:
		'Store prices come from the public data of GVH Árfigyelő. Every price is shown with its source and the data date.',
	prices_date: 'Current data date: {date}',
	prices_scope:
		'“Cheapest” always refers to the selected nearby stores and to that day’s GVH data. Where no store-level price exists, the chain’s typical price is shown and labelled as such.',
	gvh_link: 'arfigyelo.gvh.hu',

	ksh_title: 'Estimated prices (KSH)',
	ksh_text:
		'For ingredients that GVH Árfigyelő does not cover, the monthly national average price from KSH is shown, labelled “estimated national average price (KSH)”. It is not a store price and is never added to a store total.',
	ksh_license: 'The data of the KSH STADAT ara0044 table is used under the CC BY 4.0 licence.',
	ksh_period: 'KSH data period: {period}',
	ksh_link: 'KSH STADAT ara0044',
	ksh_license_link: 'CC BY 4.0 licence',

	nutrition_title: 'Nutrition',
	nutrition_text:
		'Nutrition data is not available yet. When it is, it will be computed from open food composition tables, with the source named.',

	recipes_title: 'Recipes',
	recipes_text:
		'The recipes are our own original texts. Until someone has actually cooked one, it carries the label “untested recipe”.',

	privacy_title: 'Privacy',
	device_title: 'What stays on your device',
	device_plan: 'the weekly plan and the ticks on the shopping list',
	device_household: 'the household size, the number of meals and the search radius',
	device_pantry: 'the pantry and the excluded ingredients and tags',
	device_location: 'the location permission, the chosen district or the approximate location',
	device_language: 'the chosen language',
	device_cache:
		'For offline use the browser stores the app files and the public data (store list, ingredients, recipes). This is not personal data.',

	server_title: 'What is sent to the server',
	server_recipes: 'the ids of the chosen recipes and the number of servings',
	server_ingredients: 'the ids and quantities of the ingredients',
	server_stores: 'the ids of the chosen stores',
	server_plan:
		'when you ask for a weekly plan: the number of days, meals and people, and the excluded tags and ingredients, used only for that computation',
	server_never:
		'Your location, your address or any personal identifier is never sent. The server neither stores nor logs the content of your requests.',

	cookies_title: 'Cookies and analytics',
	cookies_text: 'No cookies, no analytics, no tracking code, and no content loaded from other sites.',
	delete_text: 'You can delete your data at any time here:',
	delete_link: 'Settings',

	contact_title: 'Contact',
	contact_text: 'Contact details: coming soon.',

	disclaimer_title: 'Legal notice'
};
