<!--
	"Pont választása a térképen": the starting point for the nearby stores when the device's position is not
	available or not wanted (BUILD-BRIEF §8.8). A schematic map drawn on the device as SVG: the stores' positions
	as dots (GET /api/stores, public data; their chain and address as text labels when zoomed in), the Budapest
	districts' numerals, a scale bar. No map tiles and no request to any other site (the CSP allows none), so
	nothing about where the user looks or taps ever leaves the device. A tap (or the arrow keys, with the map
	focused) sets the point; + and − zoom (around the point when it is in view); "Budapest" and "Egész ország"
	are presets. The point is reported to the page, which stores it on this device only; the picker never shows
	the coordinates, only a hint ("XI. kerület közelében").
-->
<script lang="ts">
	import { onMount, untrack } from 'svelte';
	import { ApiError } from '$lib/api/client';
	import type { StoreOut } from '$lib/api/types';
	import { formatDistance, formatNumber } from '$lib/format';
	import type { LatLon } from '$lib/geo';
	import { t } from '$lib/i18n';
	import { DISTRICTS } from '$lib/districts';
	import { DEFAULT_FRAME, scaleBar, viewFrame } from '$lib/journey/map';
	import { loadStores } from '$lib/list/data';
	import { chainLabel, chainNames, storeAddress } from '$lib/list/stores';
	import { validStores } from '$lib/list/validate';
	import {
		BUDAPEST_VIEW,
		DISTRICT_LABEL_SPAN_KM,
		FINE_SPAN_KM,
		MAX_SPAN_KM,
		MIN_SPAN_KM,
		STORE_LABEL_SPAN_KM,
		countryView,
		describePoint,
		inView,
		nudge,
		zoomView,
		type MapView
	} from '$lib/mappick';
	import { getMeta } from '$lib/meta.svelte';
	import Spinner from './Spinner.svelte';

	interface Props {
		/** The stored map point, or null. */
		point: LatLon | null;
		onpick: (point: LatLon) => void;
		onclear: () => void;
	}

	let { point, onpick, onclear }: Props = $props();
	const id = $props.id();
	const meta = getMeta();

	const WIDTH = DEFAULT_FRAME.width;
	const HEIGHT = DEFAULT_FRAME.height;

	type StoresState = { status: 'loading' } | { status: 'ready'; stores: StoreOut[] } | { status: 'error'; error: unknown };
	let storesState = $state<StoresState>({ status: 'loading' });
	let svg = $state<SVGSVGElement>();
	// Start on the stored point (close up) or on Budapest; later changes of the point do not move the view.
	let view = $state<MapView>(untrack(() => (point ? { centre: point, spanKm: FINE_SPAN_KM } : { ...BUDAPEST_VIEW })));

	function fetchStores(): void {
		storesState = { status: 'loading' };
		loadStores()
			.then((data) => {
				const valid = validStores(data);
				storesState = valid ? { status: 'ready', stores: valid } : { status: 'error', error: new ApiError({ kind: 'invalid_response' }) };
			})
			.catch((error: unknown) => {
				storesState = { status: 'error', error };
			});
	}

	onMount(fetchStores);

	const stores = $derived(storesState.status === 'ready' ? storesState.stores : []);
	const names = $derived(chainNames(meta.data?.chains));
	const frame = $derived(viewFrame(view.centre, view.spanKm, { width: WIDTH, height: HEIGHT }));
	const inside = (p: { x: number; y: number }): boolean => p.x >= -4 && p.x <= WIDTH + 4 && p.y >= -4 && p.y <= HEIGHT + 4;
	const placed = $derived(
		stores.flatMap((store) => {
			if (store.lat === null || store.lon === null) return [];
			const at = frame.project({ lat: store.lat, lon: store.lon });
			return inside(at) ? [{ store, at }] : [];
		})
	);
	const showStoreLabels = $derived(view.spanKm <= STORE_LABEL_SPAN_KM);
	const districtLabels = $derived(
		view.spanKm <= DISTRICT_LABEL_SPAN_KM
			? DISTRICTS.flatMap((district) => {
					const at = frame.project(district);
					return inside(at) ? [{ district, at }] : [];
				})
			: []
	);
	const marker = $derived(point && inView(point, view) ? frame.project(point) : null);
	const scale = $derived(scaleBar(frame, 110));
	const scaleY = HEIGHT - 14;
	const hint = $derived(point ? describePoint(point, stores) : null);
	const hintText = $derived.by(() => {
		if (!point || !hint) return t('core.map_point_none');
		if (hint.kind === 'district') return t('core.map_point_district', { district: t('core.district_name', { roman: hint.district.roman }) });
		if (hint.kind === 'city') return t('core.map_point_city', { city: hint.city });
		return t('core.map_point_plain');
	});
	const mapLabel = $derived(
		t('core.map_label', { span: formatNumber(Math.round(view.spanKm * 10) / 10), stores: formatNumber(placed.length) })
	);

	function pickAt(x: number, y: number): void {
		const place = frame.unproject({ x, y });
		if (!Number.isFinite(place.lat) || !Number.isFinite(place.lon)) return;
		onpick(place);
	}

	function tap(event: MouseEvent): void {
		const element = svg;
		if (!element) return;
		const rect = element.getBoundingClientRect();
		if (rect.width <= 0 || rect.height <= 0) return;
		// The SVG keeps its aspect ratio (height follows the viewBox), so the box maps straight onto the viewBox.
		pickAt(((event.clientX - rect.left) / rect.width) * WIDTH, ((event.clientY - rect.top) / rect.height) * HEIGHT);
	}

	function zoom(factor: number): void {
		view = zoomView(view, factor, point && inView(point, view) ? point : null);
	}

	function keys(event: KeyboardEvent): void {
		const steps: Record<string, [number, number]> = { ArrowUp: [0, 1], ArrowDown: [0, -1], ArrowLeft: [-1, 0], ArrowRight: [1, 0] };
		const step = steps[event.key];
		if (step) {
			event.preventDefault();
			const from = point && inView(point, view) ? point : view.centre;
			const next = nudge(from, view, step[0], step[1]);
			if (!inView(next, view)) view = { ...view, centre: next };
			onpick(next);
			return;
		}
		if (event.key === '+' || event.key === '=') {
			event.preventDefault();
			zoom(0.5);
		} else if (event.key === '-') {
			event.preventDefault();
			zoom(2);
		} else if (event.key === 'Enter' && !point) {
			event.preventDefault();
			onpick(view.centre);
		}
	}
</script>

<div class="picker" data-testid="map-picker">
	<p class="small muted" id="{id}-hint">{t('core.map_pick_hint')}</p>
	<figure class="map">
		<!-- A tap or the arrow keys set the point, + and − zoom: a small application, not a picture (so the
		     tabindex and the handlers belong on it; the buttons below do the same without a pointer). -->
		<!-- svelte-ignore a11y_no_noninteractive_tabindex, a11y_no_noninteractive_element_interactions -->
		<svg
			bind:this={svg}
			viewBox="0 0 {WIDTH} {HEIGHT}"
			role="application"
			aria-labelledby="{id}-title"
			aria-describedby="{id}-hint"
			tabindex="0"
			preserveAspectRatio="xMidYMid meet"
			onclick={tap}
			onkeydown={keys}
			data-testid="map-picker-map"
		>
			<title id="{id}-title">{mapLabel}</title>
			<rect class="ground" x="0" y="0" width={WIDTH} height={HEIGHT} rx="10" />
			{#each placed as item (item.store.id)}
				<circle class="store" cx={item.at.x} cy={item.at.y} r={showStoreLabels ? 5 : 2.5} />
				{#if showStoreLabels}
					<text class="store-label" x={item.at.x + 7} y={item.at.y + 4}>
						{chainLabel(item.store.chain, names)}{storeAddress(item.store) ? `, ${storeAddress(item.store)}` : ''}
					</text>
				{/if}
			{/each}
			{#each districtLabels as item (item.district.id)}
				<text class="district" x={item.at.x} y={item.at.y} text-anchor="middle" dy="0.35em">{item.district.roman}</text>
			{/each}
			{#if marker}
				<circle class="marker-halo" cx={marker.x} cy={marker.y} r="12" />
				<circle class="marker" cx={marker.x} cy={marker.y} r="6" data-testid="map-picker-marker" />
			{/if}
			<line class="scale" x1="14" y1={scaleY} x2={14 + scale.units} y2={scaleY} />
			<line class="scale" x1="14" y1={scaleY - 5} x2="14" y2={scaleY + 1} />
			<line class="scale" x1={14 + scale.units} y1={scaleY - 5} x2={14 + scale.units} y2={scaleY + 1} />
			<text class="scale-label" x="14" y={scaleY - 8}>{formatDistance(scale.km)}</text>
		</svg>
		<figcaption class="small muted">
			{#if storesState.status === 'loading'}
				<Spinner label={t('core.map_stores_loading')} showLabel announce={false} />
			{:else}
				<span role="status" data-testid="map-picker-hint">{hintText}</span>
			{/if}
		</figcaption>
	</figure>
	<div class="controls">
		<button type="button" class="btn btn-secondary" onclick={() => zoom(0.5)} aria-disabled={view.spanKm <= MIN_SPAN_KM}>
			{t('core.map_zoom_in')}
		</button>
		<button type="button" class="btn btn-secondary" onclick={() => zoom(2)} aria-disabled={view.spanKm >= MAX_SPAN_KM}>
			{t('core.map_zoom_out')}
		</button>
		<button type="button" class="btn btn-secondary" onclick={() => (view = { ...BUDAPEST_VIEW })}>{t('core.map_view_budapest')}</button>
		<button type="button" class="btn btn-secondary" onclick={() => (view = countryView(stores))}>{t('core.map_view_country')}</button>
		{#if point}
			<button type="button" class="btn btn-ghost" onclick={onclear}>{t('core.map_clear_point')}</button>
		{/if}
	</div>
</div>

<style>
	.picker > :global(* + *) {
		margin-top: var(--space-2);
	}

	.picker p {
		margin: 0;
	}

	.map {
		margin: 0;
	}

	svg {
		display: block;
		width: 100%;
		height: auto;
		cursor: crosshair;
		touch-action: manipulation;
		border-radius: 10px;
	}

	svg:focus-visible {
		outline: var(--focus-ring);
		outline-offset: 2px;
	}

	.ground {
		fill: var(--color-surface-alt);
		stroke: var(--color-border-subtle);
	}

	.store {
		fill: var(--color-primary);
		opacity: 0.75;
	}

	.store-label,
	.district,
	.scale-label {
		fill: var(--color-text);
		font-family: var(--font-sans);
	}

	.store-label {
		font-size: 11px;
	}

	.district {
		font-size: 13px;
		font-weight: 700;
		fill: var(--color-text-muted);
	}

	.marker-halo {
		fill: var(--color-surface);
		stroke: var(--color-focus);
		stroke-width: 2;
	}

	.marker {
		fill: var(--color-focus);
	}

	.scale {
		stroke: var(--color-text);
		stroke-width: 2;
	}

	.scale-label {
		font-size: 12px;
	}

	figcaption {
		margin-top: var(--space-2);
		min-height: 1.5em;
	}

	.controls {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(min(100%, 9rem), 1fr));
		gap: var(--space-2);
	}
</style>
