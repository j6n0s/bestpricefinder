// All data in this file is SYNTHETIC test data (see README.md in this folder).
import { describe, expect, it, vi } from 'vitest';
import { memoised } from './data';

describe('memoised', () => {
	it('fetches once and shares the answer', async () => {
		const fetcher = vi.fn(() => Promise.resolve({ stores: [] }));
		const loader = memoised(fetcher);
		const [a, b] = await Promise.all([loader.get(), loader.get()]);
		expect(a).toBe(b);
		await loader.get();
		expect(fetcher).toHaveBeenCalledTimes(1);
	});

	it('forgets a failure, so a retry fetches again', async () => {
		const fetcher = vi
			.fn<() => Promise<string>>()
			.mockRejectedValueOnce(new Error('offline'))
			.mockResolvedValueOnce('ok');
		const loader = memoised(fetcher);
		await expect(loader.get()).rejects.toThrow('offline');
		await expect(loader.get()).resolves.toBe('ok');
		await expect(loader.get()).resolves.toBe('ok');
		expect(fetcher).toHaveBeenCalledTimes(2);
	});

	it('fetches again after reset', async () => {
		const fetcher = vi.fn(() => Promise.resolve(1));
		const loader = memoised(fetcher);
		await loader.get();
		loader.reset();
		await loader.get();
		expect(fetcher).toHaveBeenCalledTimes(2);
	});

	it('a failure that settles after a reset does not clear a newer request', async () => {
		let rejectFirst: (reason: Error) => void = () => undefined;
		const fetcher = vi
			.fn<() => Promise<string>>()
			.mockImplementationOnce(() => new Promise((_, reject) => (rejectFirst = reject)))
			.mockResolvedValue('fresh');
		const loader = memoised(fetcher);
		const first = loader.get();
		loader.reset();
		const second = loader.get();
		rejectFirst(new Error('late failure'));
		await expect(first).rejects.toThrow('late failure');
		await expect(second).resolves.toBe('fresh');
		await expect(loader.get()).resolves.toBe('fresh');
		expect(fetcher).toHaveBeenCalledTimes(2);
	});
});
