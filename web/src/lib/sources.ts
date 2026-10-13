/** External source links shown on the attribution line and the sources page (plain links, never fetched). */
export const GVH_URL = 'https://arfigyelo.gvh.hu';
export const KSH_URL = 'https://www.ksh.hu/stadat_files/ara/hu/ara0044.html';
export const KSH_LICENSE_URL = 'https://creativecommons.org/licenses/by/4.0/deed.hu';

/** A KSH link from /api/meta, accepted only when it points at ksh.hu over https; else the default table. */
export function safeKshUrl(url: string | null | undefined): string {
	return url && /^https:\/\/(www\.)?ksh\.hu\//.test(url) ? url : KSH_URL;
}
