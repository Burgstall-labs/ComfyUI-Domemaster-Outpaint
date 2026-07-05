"""Domemaster / fulldome rendering for ComfyUI.
Copyright Burgstall Labs (https://github.com/Burgstall-labs)

Licensed under the PolyForm Noncommercial License 1.0.0.
https://polyformproject.org/licenses/noncommercial/1.0.0
"""

import math

import torch
import torch.nn.functional as F

# Venue tilt presets: how much the physical dome leans toward the audience.
# The preset pitches the aim UP by the tilt, which slides the source content
# from "straight overhead" (flat dome) to the tilted venue's natural forward
# gaze (the sweet spot between dome center and the front springline).
_TILT_PRESETS = {
    "0 (flat dome / video at center)": 0.0,
    "15 (tilted venue)": 15.0,
    "20 (tilted venue)": 20.0,
    "25 (tilted venue)": 25.0,
    "30 (tilted venue)": 30.0,
}


class EquirectToDomemaster:
    """Render a domemaster (square 180° fisheye, fulldome format) from an
    equirectangular panorama.

    Defaults aim the dome at the canvas center (yaw 0 / pitch 0) — with the
    outpaint workflow that's exactly where Rectilinear → Equirect places the
    source video, so the original footage lands at the dome center and the
    outpainted content fills out to the rim. The equirect wrap edge (yaw 180°)
    is more than 90° away and never appears in the output.

    `dome_tilt` matches the render to a tilted venue: it pitches the aim up
    by the venue tilt so the source sits at the audience's natural gaze
    instead of straight overhead. `pitch_deg` is an additional manual offset
    (90 = classic zenith-centered domemaster). Sampling is wrap-aware across
    the equirect seam. Pixels outside the fisheye circle are black.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "size": ("INT", {"default": 2048, "min": 256, "max": 8192, "step": 64}),
                "fov_deg": ("FLOAT", {"default": 180.0, "min": 90.0, "max": 250.0, "step": 1.0,
                                      "tooltip": "Dome field of view. 180 = standard domemaster."}),
                "dome_tilt": (list(_TILT_PRESETS.keys()), {
                    "default": "0 (flat dome / video at center)",
                    "tooltip": "Physical tilt of the target venue. Pitches the aim up by "
                    "the tilt so the source content lands at the tilted dome's sweet "
                    "spot rather than straight overhead.",
                }),
                "yaw_deg": ("FLOAT", {"default": 0.0, "min": -180.0, "max": 180.0, "step": 1.0}),
                "pitch_deg": ("FLOAT", {"default": 0.0, "min": -90.0, "max": 90.0, "step": 1.0,
                                        "tooltip": "Manual aim offset, added to the tilt preset. "
                                        "0 = dome centered on the source patch, "
                                        "90 = centered on the zenith (camera-up domemaster)."}),
                "roll_deg": ("FLOAT", {"default": 0.0, "min": -180.0, "max": 180.0, "step": 1.0,
                                       "tooltip": "Rotate the dome image about its center "
                                       "(which direction is 'front'/down-screen)."}),
                "interp": (["bilinear", "bicubic"], {"default": "bicubic"}),
            },
            "optional": {
                # Angular span of the INPUT canvas. 360/180 = full equirect
                # (default). 180/180 = square-hemisphere canvas from
                # Rectilinear → Equirect with matching canvas spans.
                "input_hfov_deg": ("FLOAT", {"default": 360.0, "min": 90.0, "max": 360.0, "step": 1.0}),
                "input_vfov_deg": ("FLOAT", {"default": 180.0, "min": 90.0, "max": 180.0, "step": 1.0}),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("domemaster",)
    FUNCTION = "render"
    CATEGORY = "360/dome"

    def render(self, image, size, fov_deg, dome_tilt, yaw_deg, pitch_deg, roll_deg,
               interp, input_hfov_deg=360.0, input_vfov_deg=180.0):
        device = image.device
        B, H, W, C = image.shape
        S = int(size)
        full_wrap = input_hfov_deg >= 359.5
        h_span = math.radians(input_hfov_deg)
        v_span = math.radians(input_vfov_deg)
        aim_pitch = float(pitch_deg) + _TILT_PRESETS.get(dome_tilt, 0.0)

        # ---- Output pixel → direction on the unit sphere ----
        # Domemaster: equidistant fisheye. r (fraction of radius) → angle from
        # the optical axis theta = r * fov/2.
        half = (S - 1) / 2.0
        vv, uu = torch.meshgrid(
            torch.arange(S, device=device, dtype=torch.float32),
            torch.arange(S, device=device, dtype=torch.float32),
            indexing="ij",
        )
        dx = (uu - half) / (S / 2.0)
        dy = (vv - half) / (S / 2.0)
        if roll_deg:
            rr = math.radians(roll_deg)
            cr, sr = math.cos(rr), math.sin(rr)
            dx, dy = dx * cr - dy * sr, dx * sr + dy * cr
        r = torch.sqrt(dx * dx + dy * dy)
        inside = r <= 1.0
        r_safe = r.clamp(min=1e-8)
        theta = r * math.radians(fov_deg) / 2.0  # angle from axis
        sin_t = torch.sin(theta)
        # Camera frame: x right, y up, z forward (optical axis). Image up = scene up.
        x = sin_t * (dx / r_safe)
        y = sin_t * (-dy / r_safe)
        z = torch.cos(theta)

        # ---- Aim: pitch about x (up/down), then yaw about world-up ----
        p = math.radians(aim_pitch)
        cp, sp = math.cos(p), math.sin(p)
        y, z = y * cp + z * sp, -y * sp + z * cp
        yw = math.radians(yaw_deg)
        cy, sy = math.cos(yw), math.sin(yw)
        x, z = x * cy + z * sy, -x * sy + z * cy

        # ---- Direction → input canvas coords ----
        lat = torch.asin(y.clamp(-1.0, 1.0))
        lon = torch.atan2(x, z)
        u_eq = (lon / h_span + 0.5) * W  # pixel index space; wraps at W only for full 360
        v_eq = (0.5 - lat / v_span) * H
        # Directions outside a partial canvas render black
        in_span = (lon.abs() <= h_span / 2.0) & (lat.abs() <= v_span / 2.0)

        img = image.permute(0, 3, 1, 2).float()  # (B, C, H, W)
        if full_wrap:
            # Wrap-aware sampling: circular-pad the panorama along W
            pad = 2
            img = F.pad(img, [pad, pad, 0, 0], mode="circular")
            Wp = W + 2 * pad
            u = (u_eq % W) + pad
        else:
            Wp = W
            u = u_eq.clamp(0, W - 1)
        gx = (u / max(Wp - 1, 1)) * 2.0 - 1.0
        gy = (v_eq.clamp(0, H - 1) / max(H - 1, 1)) * 2.0 - 1.0
        grid = torch.stack([gx, gy], dim=-1).unsqueeze(0).expand(B, -1, -1, -1).contiguous()

        out = F.grid_sample(img, grid, mode=interp, padding_mode="border",
                            align_corners=True)
        out = out.permute(0, 2, 3, 1)  # (B, S, S, C)
        keep = (inside & in_span).unsqueeze(0).unsqueeze(-1).to(out.dtype)
        out = out * keep
        return (out.clamp(0.0, 1.0).to(image.dtype),)


NODE_CLASS_MAPPINGS = {
    "EquirectToDomemaster": EquirectToDomemaster,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "EquirectToDomemaster": "Equirect → Domemaster (fulldome render)",
}
