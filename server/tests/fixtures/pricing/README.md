# Pricing engine test fixtures: SYNTHETIC DATA ONLY

Everything in this folder is **synthetic test data** for `tests/test_pricing_*.py`. None of it is a
real price, product, store, chain or nutrient value, and none of it may be shown to users or used as a
data source.

- `builders.py` has small constructors for the `bpf.pricing.model` types and `synthetic_catalogue()`, a
  seeded generator of a large made-up catalogue (about 4,000 products) for the performance tests.
- Chains are fictional (`alfa`, `beta`, `gamma`, ...). Store ids and product ids are made up.
- `test_pricing_prices.py` and `test_pricing_packs.py` reuse a few amounts quoted in the research notes
  (e.g. the 294 / 699 Ft spaghetti trap, 149 / 359 Ft sour-cream packs) purely as test inputs that
  reproduce the documented traps; they are attached to fictional chains and are not a price source.
- Product names imitate the *shape* of GVH names (accent-less upper-case counter names, multi-variant
  "A/B" private labels, mis-filed SKUs) as described in `research/recipe-coverage/notes.md` §8. They are
  there to exercise the name rules, not to describe real products.
- Prices, pack sizes, piece weights, densities, KSH rows and nutrition rows are invented round numbers
  chosen so that the expected results can be computed by hand in the test comments.
