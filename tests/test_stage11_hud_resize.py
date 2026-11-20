import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from src.engine.ui.hud import FloatingHUD


class TestStage11HUDResize(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "config.json"
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump({
                "hud": {
                    "min_width": 350,
                    "min_height": 250,
                    "expanded_width": 400,
                    "expanded_height": 360,
                }
            }, f)
        self.hud = FloatingHUD(config_path=self.config_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    # ------------------------------------------------------------------
    # 1. Config Loading & Minimum Dimension Lock
    # ------------------------------------------------------------------
    def test_minimum_dimension_lock_initialization(self):
        self.assertEqual(self.hud.min_width, 350)
        self.assertEqual(self.hud.min_height, 250)
        self.assertEqual(self.hud.expanded_width, 400)
        self.assertEqual(self.hud.expanded_height, 360)

    def test_dimension_clamping_on_undersized_inputs(self):
        # Attempt to set size below minimum
        clamped_w, clamped_h = self.hud.set_dimensions(width=200, height=150)
        self.assertEqual(clamped_w, 350)
        self.assertEqual(clamped_h, 250)
        self.assertEqual(self.hud.expanded_width, 350)
        self.assertEqual(self.hud.expanded_height, 250)

    def test_dimension_expansion(self):
        # Expand size to valid dimensions
        clamped_w, clamped_h = self.hud.set_dimensions(width=600, height=500)
        self.assertEqual(clamped_w, 600)
        self.assertEqual(clamped_h, 500)
        self.assertEqual(self.hud.expanded_width, 600)
        self.assertEqual(self.hud.expanded_height, 500)

    def test_update_min_dimensions(self):
        min_w, min_h = self.hud.set_min_dimensions(min_width=450, min_height=320)
        self.assertEqual(min_w, 450)
        self.assertEqual(min_h, 320)
        self.assertEqual(self.hud.min_width, 450)
        self.assertEqual(self.hud.min_height, 320)

    def test_safety_floor_on_min_dimensions(self):
        # Enforces safety floor: min_width cannot be < 280, min_height cannot be < 180
        min_w, min_h = self.hud.set_min_dimensions(min_width=100, min_height=50)
        self.assertEqual(min_w, 280)
        self.assertEqual(min_h, 180)

    # ------------------------------------------------------------------
    # 2. Config Persistence Across Restarts
    # ------------------------------------------------------------------
    def test_config_persistence(self):
        # Resize HUD to new custom geometry
        self.hud.set_dimensions(550, 480)
        self.hud._save_geometry_to_config()

        # Verify config on disk
        with open(self.config_path, "r", encoding="utf-8") as f:
            saved_cfg = json.load(f)

        self.assertEqual(saved_cfg["hud"]["expanded_width"], 550)
        self.assertEqual(saved_cfg["hud"]["expanded_height"], 480)
        self.assertEqual(saved_cfg["hud"]["min_width"], 350)
        self.assertEqual(saved_cfg["hud"]["min_height"], 250)

        # Reload a new instance of FloatingHUD from the saved config
        reloaded_hud = FloatingHUD(config_path=self.config_path)
        self.assertEqual(reloaded_hud.expanded_width, 550)
        self.assertEqual(reloaded_hud.expanded_height, 480)
        self.assertEqual(reloaded_hud.min_width, 350)
        self.assertEqual(reloaded_hud.min_height, 250)

    # ------------------------------------------------------------------
    # 3. Simulated Mouse Drag-to-Resize Mechanics
    # ------------------------------------------------------------------
    def test_drag_to_resize_clamping(self):
        # Mock Tk root window
        mock_root = MagicMock()
        mock_root.winfo_width.return_value = 400
        mock_root.winfo_height.return_value = 360
        mock_root.winfo_screenwidth.return_value = 1920
        mock_root.winfo_screenheight.return_value = 1080
        mock_root.winfo_x.return_value = 500
        mock_root.winfo_y.return_value = 100
        self.hud.root = mock_root

        # 1. Start drag at screen (x=600, y=400)
        mock_event_start = MagicMock()
        mock_event_start.x_root = 600
        mock_event_start.y_root = 400
        self.hud._on_resize_start(mock_event_start)
        self.assertTrue(self.hud._resize_data["resizing"])

        # 2. Drag by (+100, +80)
        mock_event_drag = MagicMock()
        mock_event_drag.x_root = 700
        mock_event_drag.y_root = 480
        self.hud._on_resize_drag(mock_event_drag)
        self.assertEqual(self.hud.expanded_width, 500)
        self.assertEqual(self.hud.expanded_height, 440)

        # 3. Drag with extreme negative delta (e.g. -500, -500) -> Must clamp to minimums
        mock_event_shrink = MagicMock()
        mock_event_shrink.x_root = 100
        mock_event_shrink.y_root = 50
        self.hud._on_resize_drag(mock_event_shrink)
        self.assertEqual(self.hud.expanded_width, 350)  # Clamped to min_width
        self.assertEqual(self.hud.expanded_height, 250) # Clamped to min_height

        # 4. Release mouse -> Should finish resizing and persist
        mock_event_end = MagicMock()
        self.hud._on_resize_end(mock_event_end)
        self.assertFalse(self.hud._resize_data["resizing"])


if __name__ == "__main__":
    unittest.main()
