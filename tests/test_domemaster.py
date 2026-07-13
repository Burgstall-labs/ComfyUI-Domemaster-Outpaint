import unittest

import torch

from domemaster import EquirectToDomemaster


def coordinate_erp(height=181, width=181):
    """R increases left->right; G increases bottom->top."""
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
            batch_size=1,
            mirror_x=False,
        )
        params.update(kwargs)
        return self.node.render(**params)[0]

    def test_square_hemisphere_cardinal_directions(self):
        out = self.render()[0]
        c = 90
        self.assertAlmostEqual(out[c, c, 0].item(), 0.5, places=2)
        self.assertAlmostEqual(out[c, c, 1].item(), 0.5, places=2)
        self.assertGreater(out[c, 180, 0].item(), 0.98)  # +90 lon = right rim
        self.assertLess(out[c, 0, 0].item(), 0.02)       # -90 lon = left rim
        self.assertGreater(out[0, c, 1].item(), 0.98)    # +90 lat = top rim
        self.assertLess(out[180, c, 1].item(), 0.02)     # -90 lat = bottom rim

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


if __name__ == "__main__":
    unittest.main()
