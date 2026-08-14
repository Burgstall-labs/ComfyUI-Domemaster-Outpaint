import unittest

import torch

from domemaster import EquirectToDomemaster


def coordinate_erp(height=181, width=181):
    """R increases left-to-right; G increases bottom-to-top."""
    u = torch.arange(width, dtype=torch.float32) / max(width - 1, 1)
    v = 1.0 - torch.arange(height, dtype=torch.float32) / max(height - 1, 1)
    red = u.view(1, 1, width).expand(1, height, width)
    green = v.view(1, height, 1).expand(1, height, width)
    blue = torch.zeros_like(red)
    return torch.stack([red, green, blue], dim=-1)


class DomemasterProjectionTests(unittest.TestCase):
    def setUp(self):
        self.node = EquirectToDomemaster()
        self.image = coordinate_erp()

    def render(self, **kwargs):
        params = dict(
            image=self.image,
            size=181,
            fov_deg=180.0,
            dome_tilt="0 (flat dome / video at center)",
            yaw_deg=0.0,
            pitch_deg=0.0,
            roll_deg=0.0,
            interp="bilinear",
            input_hfov_deg=180.0,
            input_vfov_deg=180.0,
            center_crop_2_1=False,
            batch_size=1,
            mirror_x=False,
        )
        params.update(kwargs)
        return self.node.render(**params)[0]

    def test_square_hemisphere_cardinal_directions(self):
        out = self.render()[0]
        center = 90
        self.assertAlmostEqual(out[center, center, 0].item(), 0.5, places=2)
        self.assertAlmostEqual(out[center, center, 1].item(), 0.5, places=2)
        self.assertGreater(out[center, 180, 0].item(), 0.98)
        self.assertLess(out[center, 0, 0].item(), 0.02)
        self.assertGreater(out[0, center, 1].item(), 0.98)
        self.assertLess(out[180, center, 1].item(), 0.02)

    def test_default_orientation_is_not_mirrored(self):
        normal = self.render()[0][90, 135, 0]
        mirrored = self.render(mirror_x=True)[0][90, 135, 0]
        self.assertGreater(normal.item(), 0.5)
        self.assertLess(mirrored.item(), 0.5)

    def test_chunking_preserves_batch_and_result(self):
        image = self.image.expand(5, -1, -1, -1).clone()
        out = self.render(image=image, batch_size=2)
        self.assertEqual(out.shape[0], 5)
        for i in range(1, 5):
            torch.testing.assert_close(out[0], out[i])

    def test_center_crop_2_1_matches_manual_square_crop(self):
        full_erp = coordinate_erp(height=181, width=362)
        automatic = self.render(
            image=full_erp,
            input_hfov_deg=360.0,
            center_crop_2_1=True,
            yaw_deg=12.0,
        )

        crop_left = (full_erp.shape[2] - full_erp.shape[1]) // 2
        manual_crop = full_erp[
            :, :, crop_left:crop_left + full_erp.shape[1], :
        ]
        manual = self.render(
            image=manual_crop,
            input_hfov_deg=180.0,
            center_crop_2_1=False,
            yaw_deg=12.0,
        )

        torch.testing.assert_close(automatic, manual)

    def test_center_crop_rejects_portrait_input(self):
        with self.assertRaisesRegex(ValueError, "at least as wide"):
            self.render(
                image=coordinate_erp(height=181, width=90),
                center_crop_2_1=True,
            )


if __name__ == "__main__":
    unittest.main()
