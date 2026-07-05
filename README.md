# ComfyUI-Domemaster-Outpaint

Turn flat video into **fulldome / planetarium shows** with ComfyUI: outpaint a
normal perspective shot into an immersive hemisphere and render it as a
**domemaster** — the standard fulldome delivery format (square frame,
circular 180° fisheye) — with tilted-venue presets.

By **Burgstall Labs**. Built for the LTX2.3 VR-Outpaint model; works with any
pipeline that produces equirectangular imagery.

**Keywords:** ComfyUI domemaster, fulldome outpaint, planetarium video,
360 dome projection, fisheye render, tilted dome, LTX-2.3, Burgstall Labs.

## The workflow

```
[Load Video] → [Rectilinear → Equirect] → outpaint (LTX2.3 VR-Outpaint)
             → [Source Composite] → [Equirect → Domemaster] → save
```

The projection and finishing nodes come from the companion pack
[**ComfyUI-VR-Outpaint-Tools**](https://github.com/Burgstall-labs/ComfyUI-VR-Outpaint-Tools)
— install both. This pack contributes the dome-side rendering.

Two ways to run the pipeline:

- **Full 360 master**: outpaint a standard 2:1 equirect, then render the dome
  from it (rear hemisphere is simply not shown).
- **Square hemisphere (recommended for dome-only delivery)**: a hemisphere is
  exactly the center square of an equirectangular projection — an equirect
  spanning ±90° in both axes covers the dome completely, and its square
  boundary maps onto the dome rim. Set `canvas_hfov_deg=180`,
  `canvas_vfov_deg=180` on a **square canvas** in Rectilinear → Equirect,
  disable wrap/seam nodes (a hemisphere has no wrap seam), set
  `wrap_w=false` on Source Composite, and `input_hfov_deg=180`,
  `input_vfov_deg=180` here. Nothing is generated outside the dome — at equal
  generation cost, twice the pixels land on the dome (√2× the angular
  resolution per axis).

## Node: Equirect → Domemaster (fulldome render)

Renders a domemaster from an equirectangular panorama. By default the dome is
aimed at the canvas center — exactly where **Rectilinear → Equirect** places
the source footage — so the original video sits at the dome center and the
outpainted content fills out to the rim. The equirect wrap edge (yaw 180°) is
more than 90° from the aim and never appears in the output. Sampling is
wrap-aware, so off-axis aims are safe too.

| Input | Description |
|---|---|
| `image` | Equirect `IMAGE` batch (the finished panorama) |
| `size` | Output square size, e.g. `2048` or `4096` |
| `fov_deg` | Dome field of view (default `180`) |
| `dome_tilt` | Venue preset: `0` (flat dome — video straight overhead at dome center) or `15 / 20 / 25 / 30` for tilted venues — pitches the aim up by the tilt so the source lands at the audience's natural forward gaze (the sweet spot between dome center and the front springline) |
| `yaw_deg` / `pitch_deg` | Manual aim offset on top of the tilt preset. `pitch 90` = classic zenith-centered domemaster with the full horizon at the rim |
| `roll_deg` | Rotate the dome image about its center (which direction is "front") |
| `interp` | `bicubic` (default) or `bilinear` |
| `input_hfov_deg` / `input_vfov_deg` *(optional)* | Angular span of the input canvas (default `360` / `180`). Set both to `180` for a square-hemisphere input |

Pixels outside the fisheye circle are black. Keep the equirect as your master
and render the domemaster as a delivery format.

## Install

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/Burgstall-labs/ComfyUI-Domemaster-Outpaint
git clone https://github.com/Burgstall-labs/ComfyUI-VR-Outpaint-Tools   # companion pack
```

Restart ComfyUI. The node appears under `360/dome`. No dependencies beyond
the torch runtime ComfyUI already uses.

## Related Burgstall Labs work

- [ComfyUI-VR-Outpaint-Tools](https://github.com/Burgstall-labs/ComfyUI-VR-Outpaint-Tools) —
  projection prep, camera estimation, and outpaint finishing (source
  composite + tone correction).
- [ComfyUI-Seamless-Equirectangular](https://github.com/Burgstall-labs/ComfyUI-Seamless-Equirectangular) —
  seam-free 360° video generation for full-sphere masters.
- [Seamless-Equirectangular LTX2.3 LoRA](https://huggingface.co/TheBurgstall/Seamless-Equirectangular-LTX2.3-LoRA)

## License

This nodepack is licensed under the **PolyForm Noncommercial License 1.0.0**
(https://polyformproject.org/licenses/noncommercial/1.0.0). Noncommercial use
(research, academic, personal, hobbyist) is free. Commercial use requires a
separate license — contact **howdy@theaiwrangler.com**. See the LICENSE file
for details.
