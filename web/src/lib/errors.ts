import { isApiError } from './api/client';
import type { PlainKey } from './i18n/messages';

/** The user-facing message for any error thrown by the API client (or anything else). */
export function errorMessageKey(error: unknown): PlainKey {
	if (!isApiError(error)) return 'core.error_generic';
	switch (error.kind) {
		case 'offline':
			return 'core.error_offline';
		case 'network':
			return 'core.error_network';
		case 'timeout':
			return 'core.error_timeout';
		case 'invalid_response':
			return 'core.error_invalid_response';
		case 'aborted':
			return 'core.error_generic';
		case 'http':
			switch (error.code) {
				case 'rate_limited':
					return 'core.error_rate_limited';
				case 'no_data':
					return 'core.error_no_data';
				case 'not_found':
					return 'core.error_not_found';
				case 'invalid_request':
					return 'core.error_invalid_request';
				default:
					return 'core.error_generic';
			}
	}
}
