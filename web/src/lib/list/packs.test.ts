// All data in this file is SYNTHETIC test data (see README.md in this folder).
import { describe, expect, it } from 'vitest';
import type { PackOptionOut } from '../api/types';
import { formatAmount, leftoverText, listAmount, packsText, unitPriceText } from './packs';

const NBSP = '\u00a0';
const sp = (text: string): string => text.replaceAll(' ', NBSP);

function option(packSize: number | null): PackOptionOut {
	return {
		product_id: 'synthetic-1',
		product_name: 'Szintetikus termék',
		pack_size: packSize,
		pack_price: 459,
		unit_price: 2623,
		price_type: 'NORMAL',
		price_scope: 'chain',
		availability: 'confirmed'
	};
}

describe('formatAmount', () => {
	it('shows amounts below 1 kg / 1 l in g / ml', () => {
		expect(formatAmount(0.175, 'kg', 'hu')).toBe(sp('175 g'));
		expect(formatAmount(0.0625, 'kg', 'hu')).toBe(sp('62,5 g'));
		expect(formatAmount(0.5, 'l', 'hu')).toBe(sp('500 ml'));
		expect(formatAmount(0.1 + 0.2, 'kg', 'hu')).toBe(sp('300 g'));
		expect(formatAmount(0.001, 'kg', 'hu')).toBe(sp('1 g'));
	});

	it('keeps whole and larger amounts in the canonical unit, hu-HU numbers', () => {
		expect(formatAmount(1, 'kg', 'hu')).toBe(sp('1 kg'));
		expect(formatAmount(1.5, 'kg', 'hu')).toBe(sp('1,5 kg'));
		expect(formatAmount(1234.5, 'l', 'hu')).toBe(sp('1 234,5 l'));
		expect(formatAmount(10, 'db', 'hu')).toBe(sp('10 db'));
		expect(formatAmount(0.5, 'db', 'hu')).toBe(sp('0,5 db'));
	});

	it('translates the piece unit and keeps hu-HU numbers in English', () => {
		expect(formatAmount(10, 'db', 'en')).toBe(sp('10 pcs'));
		expect(formatAmount(1.5, 'kg', 'en')).toBe(sp('1,5 kg'));
		expect(formatAmount(0.25, 'kg', 'en')).toBe(sp('250 g'));
	});

	it('shows a dash for a non-finite amount', () => {
		expect(formatAmount(Number.NaN, 'kg', 'hu')).toBe('–');
		expect(formatAmount(Number.POSITIVE_INFINITY, 'kg', 'hu')).toBe('–');
	});
});

describe('packsText', () => {
	it('is "count × pack size" for whole packs', () => {
		expect(packsText({ count: 2, option: option(0.175) }, 'kg', 'hu')).toBe(sp('2 × 175 g'));
		expect(packsText({ count: 1, option: option(10) }, 'db', 'hu')).toBe(sp('1 × 10 db'));
		expect(packsText({ count: 3, option: option(1) }, 'l', 'hu')).toBe(sp('3 × 1 l'));
	});

	it('is just the count for single pieces', () => {
		expect(packsText({ count: 10, option: option(1) }, 'db', 'hu')).toBe(sp('10 db'));
	});

	it('is null for sold-by-weight picks and invalid sizes', () => {
		expect(packsText({ count: 1, option: option(null) }, 'kg', 'hu')).toBeNull();
		expect(packsText({ count: 1, option: option(0) }, 'kg', 'hu')).toBeNull();
		expect(packsText({ count: 1, option: option(Number.NaN) }, 'kg', 'hu')).toBeNull();
	});
});

describe('unitPriceText', () => {
	it('is the money per canonical unit', () => {
		expect(unitPriceText(2990, 'kg', 'hu')).toBe(sp('2 990 Ft/kg'));
		expect(unitPriceText(89.6, 'db', 'en')).toBe(sp('90 Ft/pcs'));
	});
});

describe('leftoverText', () => {
	it('mentions a real leftover only', () => {
		expect(leftoverText(0.05, 'kg', 'hu')).toBe(sp('50 g'));
		expect(leftoverText(2, 'db', 'hu')).toBe(sp('2 db'));
		expect(leftoverText(0, 'kg', 'hu')).toBeNull();
		expect(leftoverText(0.0004, 'kg', 'hu')).toBeNull();
		expect(leftoverText(null, 'kg', 'hu')).toBeNull();
		expect(leftoverText(-0.1, 'kg', 'hu')).toBeNull();
	});
});

describe('listAmount', () => {
	it('rounds pieces up to whole pieces, the way they are bought', () => {
		expect(listAmount(4.833, 'db', 'hu')).toBe(sp('5 db'));
		expect(listAmount(0.5, 'db', 'hu')).toBe(sp('1 db'));
		expect(listAmount(2, 'db', 'hu')).toBe(sp('2 db'));
		expect(listAmount(3.0000000001, 'db', 'hu')).toBe(sp('3 db'));
	});

	it('keeps at most 2 decimals for kilograms and litres, and grams and millilitres below 1', () => {
		expect(listAmount(1.384, 'kg', 'hu')).toBe(sp('1,38 kg'));
		expect(listAmount(5.048, 'l', 'hu')).toBe(sp('5,05 l'));
		expect(listAmount(1.2, 'kg', 'hu')).toBe(sp('1,2 kg'));
		expect(listAmount(0.3, 'kg', 'hu')).toBe(sp('300 g'));
		expect(listAmount(0.05, 'l', 'hu')).toBe(sp('50 ml'));
	});
});
