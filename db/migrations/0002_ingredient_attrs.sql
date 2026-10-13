-- 0002_ingredient_attrs.sql — ingredient attributes needed by the planner and the pricing engine.
-- Applied by bpf.migrate as bpf_migrator after `SET LOCAL ROLE bpf_owner` (see 0001 header).
--
-- tags              planner/nutrition-guideline facts about the ingredient itself (closed vocabulary below).
--                   The planner derives "red meat grams per person per week", "fish meal", "legume meal",
--                   "meat-free day" and "potato day" from the recipe lines through these tags.
-- perishable_days   typical shelf life after purchase/opening; NULL = shelf-stable. Used to plan leftover reuse.
-- density_kg_per_l  enables l <-> kg conversion for this ingredient only (e.g. tejföl sold per kg and per l).
--                   NULL = never convert between volume and mass.

ALTER TABLE app.ingredient
    ADD COLUMN tags text[] NOT NULL DEFAULT '{}'
        CHECK (tags <@ ARRAY[
            'red_meat', 'processed_meat', 'poultry', 'fish', 'egg', 'dairy', 'legume',
            'vegetable', 'fruit', 'potato', 'grain', 'wholegrain', 'nut_seed', 'fat_oil',
            'sweet', 'spice', 'condiment'
        ]::text[]),
    ADD COLUMN perishable_days smallint CHECK (perishable_days BETWEEN 1 AND 3650),
    ADD COLUMN density_kg_per_l numeric(6,3) CHECK (density_kg_per_l > 0 AND density_kg_per_l < 5);

-- Appending columns at the end keeps CREATE OR REPLACE VIEW valid and the existing grant on the view intact.
CREATE OR REPLACE VIEW api.ingredient AS
SELECT id, name_hu, list_group, unit, piece_weight_kg, pantry, leaf_ids, include_patterns,
       exclude_patterns, product_units, ksh_code, nutrition_code,
       tags, perishable_days, density_kg_per_l
FROM app.ingredient;
