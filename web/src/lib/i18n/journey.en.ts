import type { journeyHu } from './journey.hu';
import type { Messages } from './types';

export const journeyEn: Messages<typeof journeyHu> = {
	title: 'Where to shop',
	intro: 'Two options, {note}: everything in one store, or a short route when it pays off.',

	single_title: 'In one store',
	single_all: 'Everything is here.',
	single_all_available: 'Everything sold nearby is here.',
	single_missing_one: '{count} item is not here:',
	single_missing_other: '{count} items are not here:',
	total_label: 'To pay',
	walk_round: 'Walk there and back: about {distance}, as the crow flies.',

	journey_title_one: 'Route: {count} store',
	journey_title_other: 'Route: {count} stores',
	journey_total_label: 'In total',
	journey_saving: '{saving} cheaper than one store.',
	journey_more_one: 'This way you get {count} more item.',
	journey_more_other: 'This way you get {count} more items.',
	journey_all: 'This way you get everything.',
	journey_all_available: 'This way you get everything sold nearby.',
	journey_missing_one: '{count} item is not on the route either:',
	journey_missing_other: '{count} items are not on the route either:',
	walk_journey_longer: 'Walk: about {distance} as the crow flies, {extra} more than to one store.',
	walk_journey_shorter: 'Walk: about {distance} as the crow flies, no more than to one store.',
	stops_title: 'The route, in order',
	stop_heading: '{number}. {store}',
	leg_first: '{distance} from the starting point',
	leg_next: '{distance} from the previous store',
	leg_back: 'Back to the starting point: {distance}.',
	stop_items_one: '{count} item, {subtotal}',
	stop_items_other: '{count} items, {subtotal}',
	open_map: 'Map',
	open_map_named: 'The store on a map (OpenStreetMap, new tab): {store}',
	show_lists: 'Shopping list by store',
	hide_lists: 'Hide the list by store',
	lists_title: 'What to buy where',

	no_journey_saving: 'One store is best right now: more stores would save at most {saving}, not worth the extra walk.',
	no_journey_cheaper: 'One store is best right now: more stores would not be cheaper.',
	nowhere_one: '{count} item has no price at any nearby store:',
	nowhere_other: '{count} items have no price at any nearby store:',
	how: 'How we choose: first, getting as many items as possible; then the price. An extra store joins the route only if it saves at least {stop}, and {km} more for every extra km walked. Distances are as the crow flies; the real walk is longer.',

	map_label: 'Sketch of the route: {route}.',
	map_route_origin: 'starting point',
	map_note: 'A sketch without streets, north up.',
	map_legend_origin: 'Starting point',
	map_legend_stop: 'Store on the route',
	map_legend_nearby: 'Other nearby store'
};
