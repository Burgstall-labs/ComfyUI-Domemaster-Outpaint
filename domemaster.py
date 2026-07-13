"""Domemaster / fulldome rendering for ComfyUI.
Copyright Burgstall Labs (https://github.com/Burgstall-labs)

Licensed under the PolyForm Noncommercial License 1.0.0.
https://polyformproject.org/licenses/noncommercial/1.0.0
"""

import logging
import math

import torch
import torch.nn.functional as F

try:
    import comfy.utils as _comfy_utils
except ImportError:  # standalone test runs outside ComfyUI
    _comfy_utils = None


logger = logging.getLogger("DomemasterOutpaint")


# Venue tilt presets: how much the physical dome leans toward the audience.
_TILT_PRESETS = {
    "0 (flat dome / video at center)": 0.0,
    "15 (tilted venue)": 15.0,
    "20 (tilted venue)": 20.0,
    "25 (tilted venue)": 25.0,
    "30 (tilted venue)": 30.0,
}


class EquirectToDomemaster:
    """Render an equidistant domemaster from an equirectangular canvas.

    The Burgstall VR-Outpaint LoRA's normal 1:1 output is a 180 x 180 degree
    square hemisphere, so that is the default input span. A conventional 2:1
    full-sphere ERP remains supported by selecting 360 x 180 degrees.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "size": ("INT", {"default": 2048, "min": 256, "max": 8192, "step": 64}),
                "fov_deg": ("FLOAT", {
                    "default": 180.0, "min": 90.0, "max": 250.0, "step": 1.0,
                    "tooltip": "Dome field of view. 180 = standard domemaster.",
                }),
                "dome_tilt": (list(_TILT_PRESETS.keys()), {
                    "default": "0 (flat dome / video at center)",
                    "tooltip": "Creative framing preset for a tilted venue. Adds an upward "
                    "aim offset; confirm the final orientation against the venue's convention.",
                }),
                "yaw_deg": ("FLOAT", {"default": 0.0, "min": -180.0, "max": 180.0, "step": 1.0}),
                "pitch_deg": ("FLOAT", {
                    "default": 0.0, "min": -90.0, "max": 90.0, "step": 1.0,
                    "tooltip": "Manual aim offset added to dome_tilt. 0 centers the LoRA's "
                    "source direction; 90 centers the original ERP zenith.",
                }),
                "roll_deg": ("FLOAT", {
                    "default": 0.0, "min": -180.0, "max": 180.0, "step": 1.0,
                    "tooltip": "Rotate the domemaster about its center.",
                }),
                "interp": (["bilinear", "bicubic"], {"default": "bicubic"}),
            },
            "optional": {
                "input_hfov_deg": ("FLOAT", {
                    "default": 180.0, "min": 90.0, "max": 360.0, "step": 1.0,
                    "tooltip": "Angular width of the input. Use 180 for the LoRA's 1:1 "
                    "square hemisphere; 360 for a conventional 2:1 full ERP.",
                }),
                "input_vfov_deg": ("FLOAT", {
                    "default": 180.0, "min": 90.0, "max": 180.0, "step": 1.0,
                    "tooltip": "Angular height of the input. The VR-Outpaint LoRA uses 180.",
                }),
                "batch_size": ("INT", {
                    "default": 8, "min": 1, "max": 256, "step": 1,
                    "tooltip": "Frames rendered per GPU chunk. Lower this if a large video "
                    "runs out of VRAM; it does not change the result.",
                }),
                "mirror_x": ("BOOLEAN", {
                    "default": False,
                    "tooltip": "Mirror left/right for a venue or viewer that expects an "
                    "outside-dome convention. Leave off for Burgstall VR-Outpaint output.",
                }),
            },
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("domemaster",)
    FUNCTION = "render"
    CATEGORY = "360/dome"

    @torch.inference_mode()
    def render(self, image, size, fov_deg, dome_tilt, yaw_deg, pitch_deg, roll_deg,
               interp, input_hfov_deg=180.0, input_vfov_deg=180.0,
               batch_size=8, mirror_x=False):
        device = image.device
        B, H, W, C = image.shape
        if B == 0 or H == 0 or W == 0:
            raise ValueError("EquirectToDomemaster received an empty IMAGE batch")

        S = int(size)
        chunk_size = max(1, int(batch_size))
        full_wrap = input_hfov_deg >= 359.5
        h_span = math.radians(float(input_hfov_deg))
        v_span = math.radians(float(input_vfov_deg))
        aim_pitch = float(pitch_deg) + _TILT_PRESETS.get(dome_tilt, 0.0)

        expected_ratio = float(input_hfov_deg) / float(input_vfov_deg)
        actual_ratio = W / H
        if abs(actual_ratio / expected_ratio - 1.0) > 0.05:
            logger.warning(
                "Input is %dx%d (aspect %.3f) but angular spans %.1fx%.1f expect %.3f. "
                "For Burgstall VR-Outpaint 1:1 output use 180x180; for a full 2:1 ERP use 360x180.",
                W, H, actual_ratio, input_hfov_deg, input_vfov_deg, expected_ratio,
            )

        logger.info(
            "EquirectToDomemaster: %d frames %dx%d -> %dx%d, input span %.1fx%.1f, "
            "chunk=%d, mirror_x=%s",
            B, W, H, S, S, input_hfov_deg, input_vfov_deg, chunk_size, mirror_x,
        )

        # Output pixel -> direction on the unit sphere. This follows the same
        # longitude convention as RectilinearToEquirect in VR-Outpaint-Tools:
        # longitude increases to image-right, latitude increases upward.
        half = (S - 1) / 2.0
        vv, uu = torch.meshgrid(
            torch.arange(S, device=device, dtype=torch.float32),
            torch.arange(S, device=device, dtype=torch.float32),
            indexing="ij",
        )
        dx = (uu - half) / (S / 2.0)
        dy = (vv - half) / (S / 2.0)
        if mirror_x:
            dx = -dx
        if roll_deg:
            rr = math.radians(float(roll_deg))
            cr, sr = math.cos(rr), math.sin(rr)
            dx, dy = dx * cr - dy * sr, dx * sr + dy * cr

        r = torch.sqrt(dx * dx + dy * dy)
        inside = r <= 1.0
        theta = r * math.radians(float(fov_deg)) / 2.0
        sin_t = torch.sin(theta)
        r_safe = r.clamp(min=1e-8)
        x = sin_t * (dx / r_safe)
        y = sin_t * (-dy / r_safe)
        z = torch.cos(theta)

        # Aim: pitch about camera-right, then yaw about world-up.
        p = math.radians(aim_pitch)
        cp, sp = math.cos(p), math.sin(p)
        y, z = y * cp + z * sp, -y * sp + z * cp
        yw = math.radians(float(yaw_deg))
        cy, sy = math.cos(yw), math.sin(yw)
        x, z = x * cy + z * sy, -x * sy + z * cy

        lat = torch.asin(y.clamp(-1.0, 1.0))
        lon = torch.atan2(x, z)

        # Deliberately matches VR-Outpaint-Tools' ERP convention exactly:
        # lon = (u / W - 0.5) * span and lat = (0.5 - v / H) * span.
        u_eq = (lon / h_span + 0.5) * W
        v_eq = (0.5 - lat / v_span) * H
        in_span = (lon.abs() <= h_span / 2.0) & (lat.abs() <= v_span / 2.0)

        pad = 2 if full_wrap else 0
        Wp = W + 2 * pad
        if full_wrap:
            u = (u_eq % W) + pad
        else:
            u = u_eq.clamp(0, W - 1)
        gx = (u / max(Wp - 1, 1)) * 2.0 - 1.0
        gy = (v_eq.clamp(0, H - 1) / max(H - 1, 1)) * 2.0 - 1.0
        grid = torch.stack([gx, gy], dim=-1).unsqueeze(0)
        keep = (inside & in_span).unsqueeze(0).unsqueeze(-1)
        del uu, vv, dx, dy, r, theta, sin_t, r_safe, x, y, z
        del lat, lon, u_eq, v_eq, in_span, inside, u, gx, gy

        # Geometry is shared by every frame. Chunking avoids the old BxSxSx2
        # contiguous grid copy and avoids converting the entire video to fp32
        # at once. The final IMAGE batch still has to fit, but peak VRAM is much
        # lower and batch_size provides a predictable escape hatch.
        result = torch.empty((B, S, S, C), device=device, dtype=image.dtype)
        pbar = _comfy_utils.ProgressBar(B) if _comfy_utils is not None else None
        for start in range(0, B, chunk_size):
            end = min(start + chunk_size, B)
            img = image[start:end].permute(0, 3, 1, 2).float()
            if full_wrap:
                img = F.pad(img, [pad, pad, 0, 0], mode="circular")
            chunk_grid = grid.expand(end - start, -1, -1, -1)
            out = F.grid_sample(
                img, chunk_grid, mode=interp, padding_mode="border", align_corners=True,
            )
            out = out.permute(0, 2, 3, 1)
            out = out * keep
            result[start:end].copy_(out.clamp(0.0, 1.0).to(image.dtype))
            if pbar:
                pbar.update(end - start)

        return (result,)


NODE_CLASS_MAPPINGS = {
    "EquirectToDomemaster": EquirectToDomemaster,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "EquirectToDomemaster": "Equirect → Domemaster (fulldome render)",
}
