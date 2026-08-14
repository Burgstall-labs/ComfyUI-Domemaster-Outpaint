# Domemaster geometry calibration

These deterministic charts separate projection testing from LoRA behavior.

## Files

- `erp_360x180_angular_grid_4096x2048.png`: full 2:1, 360° × 180° ERP.
- `hemisphere_180x180_center_crop_2048x2048.png`: exact center-square crop
  of the full ERP, representing 180° × 180°.
- `domemaster_equidistant_reference_2048.png`: visual guide for the expected
  equidistant fisheye geometry.

## Direct node checks

1. Feed the hemisphere image to **Equirect → Domemaster** with
   `input_hfov_deg=180`, `input_vfov_deg=180`, and
   `center_crop_2_1=false`.
2. Feed the full ERP with `center_crop_2_1=true`. This should match the first
   result.
3. Feed the full ERP with `input_hfov_deg=360`,
   `input_vfov_deg=180`, and `center_crop_2_1=false` to test full-sphere
   sampling.

For all three checks, initially use `fov_deg=180`, `dome_tilt=0`,
`yaw_deg=0`, `pitch_deg=0`, `roll_deg=0`, and `mirror_x=false`.

In the correct domemaster:

- the yellow forward intersection lands at the exact center;
- the cyan ±90° hemisphere boundary lands on the circular rim;
- orange 15° angular rings become concentric circles with equal radial spacing;
- green 30° bearing spokes become straight radial lines;
- left, right, zenith, and nadir land on their labeled rim positions.

The domemaster reference is a visual geometry guide, not a pixel-for-pixel
golden image; source labels undergo projection and interpolation.

## Regenerate

Run from the repository root using an environment with Pillow:

```bash
/home/juho/ComfyUI/venv/bin/python calibration/generate_calibration_images.py
```
