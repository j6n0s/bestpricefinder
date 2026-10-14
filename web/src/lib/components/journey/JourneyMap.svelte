<!--
	A schematic map of a shopping route, drawn on the device as SVG: the starting point, the stops numbered in
	walking order, the way there (solid) and back (dashed), other nearby stores as small dots, a scale bar.
	No map tiles and no request to any other site (the CSP allows none): just the points' relative positions.
	The same information is in the text list next to it; the SVG has a short text alternative.
-->
<script lang="ts">
	import { formatDistance } from '$lib/format';
	import type { LatLon } from '$lib/geo';
	import { t } from '$lib/i18n';
	import { DEFAULT_FRAME, mapFrame, pathData, scaleBar, type MapPoint } from '$lib/journey/map';

	interface Stop {
		point: LatLon;
		/** Shown in the marker (1, 2, 3). */
		number: number;
		/** For the text alternative: chain and address. */
		label: string;
	}

	interface Props {
		origin: LatLon;
		stops: readonly Stop[];
		/** Other nearby stores (shown when they fall inside the map). */
		others?: readonly LatLon[];
	}

	let { origin, stops, others = [] }: Props = $props();
	const id = $props.id();

	const frame = $derived(mapFrame([origin, ...stops.map((stop) => stop.point)]));
	const start = $derived(frame.project(origin));
	const points = $derived(stops.map((stop) => ({ ...frame.project(stop.point), number: stop.number })));
	const way = $derived(pathData([start, ...points]));
	const last = $derived(points.at(-1));
	const back = $derived(last ? pathData([last, start]) : '');
	const inside = (p: MapPoint): boolean => p.x >= 6 && p.x <= DEFAULT_FRAME.width - 6 && p.y >= 6 && p.y <= DEFAULT_FRAME.height - 6;
	const dots = $derived(others.map((point) => frame.project(point)).filter(inside));
	const scale = $derived(scaleBar(frame, 110));
	const scaleY = DEFAULT_FRAME.height - 14;
	const routeText = $derived(
		[t('journey.map_route_origin'), ...stops.map((stop) => `${stop.number}. ${stop.label}`), t('journey.map_route_origin')].join(' → ')
	);
</script>

<figure class="journey-map" data-testid="journey-map">
	<svg
		viewBox="0 0 {DEFAULT_FRAME.width} {DEFAULT_FRAME.height}"
		role="img"
		aria-labelledby="{id}-title"
		preserveAspectRatio="xMidYMid meet"
	>
		<title id="{id}-title">{t('journey.map_label', { route: routeText })}</title>
		<rect class="ground" x="0" y="0" width={DEFAULT_FRAME.width} height={DEFAULT_FRAME.height} rx="10" />
		{#each dots as dot, index (index)}
			<circle class="other" cx={dot.x} cy={dot.y} r="3.5" />
		{/each}
		<path class="route" d={way} />
		{#if back}
			<path class="route back" d={back} />
		{/if}
		<circle class="origin-halo" cx={start.x} cy={start.y} r="11" />
		<circle class="origin" cx={start.x} cy={start.y} r="6" />
		{#each points as point (point.number)}
			<circle class="stop" cx={point.x} cy={point.y} r="12" data-testid="map-stop" />
			<text class="stop-number" x={point.x} y={point.y} dy="0.35em" text-anchor="middle">{point.number}</text>
		{/each}
		<line class="scale" x1="14" y1={scaleY} x2={14 + scale.units} y2={scaleY} />
		<line class="scale" x1="14" y1={scaleY - 5} x2="14" y2={scaleY + 1} />
		<line class="scale" x1={14 + scale.units} y1={scaleY - 5} x2={14 + scale.units} y2={scaleY + 1} />
		<text class="scale-label" x="14" y={scaleY - 8}>{formatDistance(scale.km)}</text>
	</svg>
	<figcaption class="small muted">
		<span class="legend"><span class="swatch swatch-origin" aria-hidden="true"></span>{t('journey.map_legend_origin')}</span>
		<span class="legend"><span class="swatch swatch-stop" aria-hidden="true"></span>{t('journey.map_legend_stop')}</span>
		{#if dots.length > 0}
			<span class="legend"><span class="swatch swatch-other" aria-hidden="true"></span>{t('journey.map_legend_nearby')}</span>
		{/if}
	</figcaption>
</figure>

<style>
	.journey-map {
		margin: 0;
	}

	svg {
		display: block;
		width: 100%;
		height: auto;
		max-height: 22rem;
	}

	.ground {
		fill: var(--color-surface-alt);
		stroke: var(--color-border-subtle);
	}

	.other {
		fill: var(--color-border);
		opacity: 0.55;
	}

	.route {
		fill: none;
		stroke: var(--color-primary);
		stroke-width: 3;
		stroke-linecap: round;
		stroke-linejoin: round;
	}

	.back {
		stroke-dasharray: 6 6;
		opacity: 0.7;
	}

	.origin-halo {
		fill: var(--color-surface);
		stroke: var(--color-focus);
		stroke-width: 2;
	}

	.origin {
		fill: var(--color-focus);
	}

	.stop {
		fill: var(--color-primary);
		stroke: var(--color-surface);
		stroke-width: 2;
	}

	.stop-number {
		fill: var(--color-on-primary);
		font-size: 13px;
		font-weight: 700;
		font-family: var(--font-sans);
	}

	.scale {
		stroke: var(--color-text);
		stroke-width: 2;
	}

	.scale-label {
		fill: var(--color-text);
		font-size: 12px;
		font-family: var(--font-sans);
	}

	figcaption {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-1) var(--space-3);
		margin-top: var(--space-2);
	}

	.legend {
		display: inline-flex;
		align-items: center;
		gap: var(--space-1);
	}

	.swatch {
		display: inline-block;
		width: 0.75rem;
		height: 0.75rem;
		border-radius: 50%;
	}

	.swatch-origin {
		/* Room for the 3px ring drawn by the shadow. */
		margin-inline: 3px;
		background: var(--color-focus);
		box-shadow: 0 0 0 2px var(--color-surface), 0 0 0 3px var(--color-focus);
	}

	.swatch-stop {
		background: var(--color-primary);
	}

	.swatch-other {
		background: var(--color-border);
		opacity: 0.55;
	}
</style>
