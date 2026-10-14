/**
 * "Hol vásárolj?": the best single store and the best route through several nearby stores
 * (src/lib/journey/journey.ts), on the list page and in the cart. Prices are always scoped and dated
 * (BUILD-BRIEF §8.6); distances are as the crow flies and say so.
 */
export const journeyHu = {
	title: 'Hol vásárolj?',
	intro: 'Két lehetőség, {note}: minden egy boltban, vagy egy rövid körút, ha az megéri.',

	single_title: 'Egy boltban',
	single_all: 'Itt minden megvan.',
	single_all_available: 'Itt minden megvan, ami a közelben kapható.',
	single_missing_one: '{count} tétel itt nincs:',
	single_missing_other: '{count} tétel itt nincs:',
	total_label: 'Fizetendő',
	walk_round: 'Séta oda-vissza: kb. {distance}, légvonalban.',

	journey_title_one: 'Körút: {count} bolt',
	journey_title_other: 'Körút: {count} bolt',
	journey_total_label: 'Összesen',
	journey_saving: '{saving}-tal olcsóbb, mint egy boltban.',
	journey_more_one: 'Így {count} tétellel többet kapsz meg.',
	journey_more_other: 'Így {count} tétellel többet kapsz meg.',
	journey_all: 'Így mindent megkapsz.',
	journey_all_available: 'Így mindent megkapsz, ami a közelben kapható.',
	journey_missing_one: '{count} tétel a körúton sincs:',
	journey_missing_other: '{count} tétel a körúton sincs:',
	walk_journey_longer: 'Séta: kb. {distance} légvonalban, {extra}-rel több, mint egy boltba.',
	walk_journey_shorter: 'Séta: kb. {distance} légvonalban, nem több, mint egy boltba.',
	stops_title: 'A körút sorrendje',
	stop_heading: '{number}. {store}',
	leg_first: '{distance} a kiindulási ponttól',
	leg_next: '{distance} az előző bolttól',
	leg_back: 'Vissza a kiindulási pontig: {distance}.',
	stop_items_one: '{count} tétel, {subtotal}',
	stop_items_other: '{count} tétel, {subtotal}',
	open_map: 'Térkép',
	open_map_named: 'A bolt helye térképen (OpenStreetMap, új lapon): {store}',
	show_lists: 'Bevásárlólista boltonként',
	hide_lists: 'A boltonkénti lista elrejtése',
	lists_title: 'Mit hol vegyél?',

	no_journey_saving: 'Most egy bolt a legjobb: több boltba menni legfeljebb {saving}-ot spórolna, ami nem éri meg a plusz utat.',
	no_journey_cheaper: 'Most egy bolt a legjobb: több boltban nem lenne olcsóbb.',
	nowhere_one: '{count} tételnek egyik közeli boltban sincs ára:',
	nowhere_other: '{count} tételnek egyik közeli boltban sincs ára:',
	how: 'Hogyan választunk? Előbb az számít, hogy minél több tételt megkapj, aztán az ár. Egy plusz bolt csak akkor kerül a körútba, ha legalább {stop}-ot spórolsz vele, és minden plusz kilométerért további {km}-ot. A távolság légvonalban értendő, a valódi gyalogút hosszabb.',

	map_label: 'A körút vázlata: {route}.',
	map_route_origin: 'kiindulási pont',
	map_note: 'Vázlat utcák nélkül, észak felül.',
	map_legend_origin: 'Kiindulási pont',
	map_legend_stop: 'Bolt a körúton',
	map_legend_nearby: 'Más közeli bolt'
} as const;
