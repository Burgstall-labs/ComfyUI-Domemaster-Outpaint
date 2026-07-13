# ComfyUI-Domemaster-Outpaint

Turn flat video into **fulldome / planetarium shows** with ComfyUI. The pack
renders the 1:1 square-hemisphere output of the
[Burgstall LTX2.3 VR-Outpaint IC-LoRA](https://huggingface.co/TheBurgstall/VR-360-Outpaint-LTX2.3-IC-LoRA)
as a standard square, circular, equidistant **domemaster**.

## Workflow

```text
[Load Video] → [Rectilinear → Equirect] → VR-Outpaint LoRA
             → [Source Composite] → [Equirect → Domemaster] → save
```

Projection and finishing nodes come from
[ComfyUI-VR-Outpaint-Tools](https://github.com/Burgstall-labs/ComfyUI-VR-Outpaint-Tools).

## Important: the LoRA output is a square hemisphere

The recommended VR-Outpaint workflow outputs a **1:1 equirectangular canvas
covering 180° horizontally and 180° vertically**. It is one hemisphere, not a
360° panorama squeezed into a square. This node therefore defaults to
`input_hfov_deg=180` and `input_vfov_deg=180`.

For a conventional 2:1 full-sphere equirectangular input, change the input
spans to `360` and `180`. A warning is logged if the image aspect ratio and the
selected angular spans disagree.

The default orientation matches VR-Outpaint-Tools: longitude increases toward
image-right and latitude upward. Leave `mirror_x=false`. The mirror switch is
provided only for viewers or venue systems using an outside-dome convention.

## Node: Equirect → Domemaster

| Input | Description |
|---|---|
| `image` | Finished equirectangular `IMAGE` batch |
| `size` | Square output size, e.g. 2048 or 4096 |
| `fov_deg` | Fisheye field of view; 180 is the standard dome hemisphere |
| `dome_tilt` | Creative framing preset for tilted venues; verify against the venue's master convention |
| `yaw_deg` / `pitch_deg` | Manual aim offsets; pitch 0 centers the original source direction |
| `roll_deg` | Rotate the domemaster about its center |
| `interp` | Bicubic or bilinear sampling |
| `input_hfov_deg` / `input_vfov_deg` | Input angular span; defaults to 180 / 180 for the LoRA's 1:1 output |
| `batch_size` | GPU render chunk size; lower it if a large video runs out of VRAM |
| `mirror_x` | Optional left/right mirror; off is correct for Burgstall VR-Outpaint |

Pixels outside the fisheye circle, and directions outside a partial input
canvas, render black. Keep the equirectangular video as the master and use the
domemaster as the delivery render.

## Memory behavior

All frames share one projection grid. Frames are sampled in configurable
chunks and written directly into the output tensor, avoiding the previous
batch-sized grid copy and full-batch float32 conversion. Output resolution and
the final ComfyUI image batch still consume VRAM; reduce `batch_size`, `size`,
or the upstream video batch if necessary.

## Install

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/Burgstall-labs/ComfyUI-Domemaster-Outpaint
git clone https://github.com/Burgstall-labs/ComfyUI-VR-Outpaint-Tools
```

Restart ComfyUI. The node appears under `360/dome`. No additional runtime
dependencies are required beyond ComfyUI's PyTorch installation.

## Tests

From the repository root in a Python environment with PyTorch:

```bash
python -m unittest discover -s tests
```

The coordinate-map tests verify the center and all four dome-rim directions,
the default non-mirrored inside view, the optional mirror, and chunked batches.

## License

PolyForm Noncommercial License 1.0.0. Noncommercial use is free. Commercial
use requires a separate license; contact **howdy@theaiwrangler.com**.
