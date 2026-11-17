# SPDX-FileCopyrightText: 2026 Frank Winter <https://www.frankwinter.com/>
# SPDX-License-Identifier: GPL-3.0-or-later

"""Remap painted cells when the palette grid changes (plan step 2)."""

import copy
import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "addon"))
sys.path.insert(0, str(ROOT / "tests"))

from model import faces
from model import palette as P
from model import remap as R
from test_palette_groups import _classic_params, _stylized_palette


def _ids(palette):
    return [c["id"] for c, _part in P.grid_columns(palette)]


class TestAutomatic(unittest.TestCase):
    def setUp(self):
        self.old = _stylized_palette()

    def test_identity(self):
        plan = R.plan_remap(self.old, copy.deepcopy(self.old))
        self.assertTrue(plan.is_identity)
        self.assertFalse(plan.needs_confirmation)
        self.assertEqual(len(plan.automatic), 22 * 5)

    def test_color_only_change_is_identity(self):
        new = copy.deepcopy(self.old)
        new["groups"][2]["chroma"] = 0.12
        new["warmth"] = -0.4
        self.assertTrue(R.plan_remap(self.old, new).is_identity)

    def test_add_column_shifts_x(self):
        new = copy.deepcopy(self.old)
        new["groups"][0]["columns"].insert(1, {"id": "neu", "name": "Neu", "hue": 10})
        plan = R.plan_remap(self.old, new)
        self.assertFalse(plan.needs_confirmation)
        self.assertFalse(plan.is_identity)
        self.assertEqual(plan.automatic[(1, 3)], (1, 3))   # Grau part 1 stays
        self.assertEqual(plan.automatic[(2, 3)], (3, 3))   # Kühl moves right
        self.assertEqual(plan.automatic[(21, 0)], (22, 0))  # Magenta

    def test_move_group_and_column(self):
        new = copy.deepcopy(self.old)
        new["groups"].insert(0, new["groups"].pop())       # Akzent first
        natur = new["groups"][2]["columns"]
        natur.append(natur.pop(0))                         # Rost to the end
        plan = R.plan_remap(self.old, new)
        self.assertFalse(plan.needs_confirmation)
        old_ids, new_ids = _ids(self.old), _ids(new)
        for (ox, oy), (nx, ny) in plan.automatic.items():
            self.assertEqual(old_ids[ox], new_ids[nx])
            self.assertEqual(oy, ny)
        self.assertEqual(plan.automatic[(4, 2)], (21, 2))  # Rost

    def test_widen_span(self):
        new = copy.deepcopy(self.old)
        new["groups"][0]["columns"][1]["span"] = 2         # Kühl 1 -> 2
        plan = R.plan_remap(self.old, new)
        self.assertFalse(plan.needs_confirmation)
        self.assertEqual(plan.automatic[(2, 4)], (2, 4))
        self.assertEqual(plan.automatic[(3, 0)], (4, 0))   # Warm moves right

    def test_classic_cols_change_keeps_equal_hues(self):
        old = P.palette_from_params(_classic_params(cols=16))
        new = P.palette_from_params(_classic_params(cols=8))
        used = {(0, 0): 3, (3, 4): 2, (2, 4): 5}           # grey, hue 2/16, hue 1/16
        plan = R.plan_remap(old, new, used)
        self.assertEqual(plan.automatic, {(0, 0): (0, 0), (3, 4): (2, 4)})
        self.assertEqual([row.old_cell for row in plan.table], [(2, 4)])
        self.assertEqual(plan.affected_faces, 5)


class TestTable(unittest.TestCase):
    def setUp(self):
        self.old = _stylized_palette()

    def test_deleted_column_suggests_nearest_overall(self):
        new = copy.deepcopy(self.old)
        new["groups"][2]["columns"].pop(0)                 # delete Rot
        used = {(12, 2): 7, (13, 2): 1}                    # Rot, Orange
        plan = R.plan_remap(self.old, new, used)
        self.assertTrue(plan.needs_confirmation)
        self.assertEqual(plan.automatic, {(13, 2): (12, 2)})
        (row,) = plan.table
        self.assertEqual((row.old_cell, row.faces, row.column_kept), ((12, 2), 7, False))
        # The suggestion is the closest color of the whole new palette.
        self.assertEqual(row.suggestion, self._nearest_brute(self.old, (12, 2), new))

    def test_rows_change_stays_in_column(self):
        new = copy.deepcopy(self.old)
        new["rows"] = 7
        plan = R.plan_remap(self.old, new)
        self.assertEqual(plan.automatic, {})
        self.assertEqual(len(plan.table), 22 * 5)
        new_ids = _ids(new)
        old_ids = _ids(self.old)
        for row in plan.table:
            self.assertTrue(row.column_kept)
            self.assertEqual(new_ids[row.suggestion[0]], old_ids[row.old_cell[0]])
        by_cell = {row.old_cell: row.suggestion for row in plan.table}
        # Ends of a ramp map to the ends of the longer ramp.
        self.assertEqual(by_cell[(5, 0)], (5, 0))
        self.assertEqual(by_cell[(5, 4)], (5, 6))

    def test_narrow_span(self):
        new = copy.deepcopy(self.old)
        new["groups"][0]["columns"][0]["span"] = 1         # Grau 2 -> 1
        used = {(0, 1): 1, (1, 3): 4}
        plan = R.plan_remap(self.old, new, used)
        self.assertEqual(plan.automatic, {(0, 1): (0, 1)})
        (row,) = plan.table
        self.assertEqual(row.old_cell, (1, 3))
        self.assertTrue(row.column_kept)
        self.assertEqual(row.suggestion[0], 0)             # still Grau

    def test_classic_to_stylized(self):
        old = P.palette_from_params(_classic_params(color_mode="OKLCH"))
        plan = R.plan_remap(old, self.old, {(0, 0): 1, (0, 8): 1})
        self.assertEqual(plan.automatic, {})
        rows = {row.old_cell: row for row in plan.table}
        self.assertEqual(rows[(0, 0)].suggestion, (0, 0))  # white -> lightest grey
        self.assertEqual(rows[(0, 8)].suggestion, (1, 4))  # black -> darkest grey

    def test_overrides(self):
        new = copy.deepcopy(self.old)
        new["groups"][2]["columns"].pop(0)
        plan = R.plan_remap(self.old, new, {(12, 2): 7, (14, 0): 1})
        mapping = plan.mapping({(12, 2): (20, 1)})
        self.assertEqual(mapping, {(12, 2): (20, 1), (14, 0): (13, 0)})
        self.assertEqual(plan.mapping()[(12, 2)], plan.table[0].suggestion)
        with self.assertRaises(ValueError):
            plan.mapping({(12, 2): (21, 0)})               # outside 21 x 5
        with self.assertRaises(ValueError):
            plan.mapping({(14, 0): (0, 0)})                # not in the table

    @staticmethod
    def _nearest_brute(old, cell, new):
        lab = P.srgb_to_oklab(*P.color_at(*cell, old)[:3])
        cols, rows = P.cell_count(new)
        return min(((x, y) for x in range(cols) for y in range(rows)),
                   key=lambda c: sum((u - v) ** 2 for u, v in zip(
                       P.srgb_to_oklab(*P.color_at(*c, new)[:3]), lab)))


class TestUv(unittest.TestCase):
    def test_count_and_remap_roundtrip(self):
        old = _stylized_palette()
        new = copy.deepcopy(old)
        new["groups"].insert(0, new["groups"].pop())
        uvs = [faces.encode_palette_uv(x, y, 22, 5)
               for x, y in [(4, 2), (4, 2), (0, 0), (21, 4)]]
        used = R.count_cells(uvs, 22, 5)
        self.assertEqual(used, {(4, 2): 2, (0, 0): 1, (21, 4): 1})
        plan = R.plan_remap(old, new, used)
        mapping = plan.mapping()
        for uv in uvs:
            old_cell = faces.decode_palette_uv(uv, 22, 5)
            new_uv = R.remap_uv(uv, plan, mapping)
            self.assertEqual(faces.decode_palette_uv(new_uv, 22, 5), mapping[old_cell])
        self.assertEqual(mapping[(21, 4)], (9, 4))         # Magenta, Akzent first

    def test_invalid_cells(self):
        old = _stylized_palette()
        # An unpainted face's default UV (0, 0) decodes to row 5 of 5.
        used = R.count_cells([(0.0, 0.0)], 22, 5)
        plan = R.plan_remap(old, copy.deepcopy(old), used)
        self.assertEqual(plan.invalid, {(0, 5): 1})
        self.assertIsNone(R.remap_uv((0.0, 0.0), plan, plan.mapping()))

    def test_grid_size_change_rescales_uv(self):
        old = _stylized_palette()
        new = copy.deepcopy(old)
        new["groups"][1]["columns"].append({"id": "neu", "name": "Neu", "hue": 10})
        plan = R.plan_remap(old, new)
        uv = faces.encode_palette_uv(21, 3, 22, 5)
        self.assertEqual(R.remap_uv(uv, plan, plan.mapping()),
                         faces.encode_palette_uv(22, 3, 23, 5))


class TestOklab(unittest.TestCase):
    def test_roundtrip(self):
        for rgb in [(1, 1, 1), (0, 0, 0), (0.8, 0.2, 0.1), (0.1, 0.5, 0.9), (0.5, 0.5, 0.5)]:
            back = P._oklab_to_srgb(*P.srgb_to_oklab(*rgb))
            for u, v in zip(back, rgb):
                self.assertAlmostEqual(u, v, places=5)


if __name__ == "__main__":
    unittest.main()
