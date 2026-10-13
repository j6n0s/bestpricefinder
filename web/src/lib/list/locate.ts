/**
 * "Saját helyzetem használata" on the list page: one approximate position from the browser, asked only from
 * the user's click on the explanation card (OriginChooser), through `requestApproxPosition` of $lib/location
 * (low accuracy, rounded to about 100 m, error mapping, never rejects) with a 10 s timeout. The position stays
 * on the device: distances are computed by $lib/geo and only store ids are sent to /api/quote.
 */
import { requestApproxPosition, type LocateEnvironment, type LocateResult } from '../location';

export const LIST_GEO_TIMEOUT_MS = 10_000;

/** Asks the browser once (call only from the user's click on the explanation card). Never rejects. */
export function locateForList(env?: LocateEnvironment): Promise<LocateResult> {
	return requestApproxPosition({ timeoutMs: LIST_GEO_TIMEOUT_MS }, env);
}
