<!--
	The one line shown next to the "use my location" buttons (BUILD-BRIEF §8.8): the position stays on this
	device, and the full explanation is on the sources and privacy page.
-->
<script lang="ts">
	import { t } from '$lib/i18n';
</script>

<p class="small muted" data-testid="location-privacy">
	{t('core.location_privacy')}
	<a href="/forrasok#src-privacy">{t('core.privacy_link')}</a>
</p>
