# ComfyUI-Domemaster-Outpaint

Turn flat video into **fulldome / planetarium shows** with ComfyUI. The pack
renders equirectangular output from the
[Burgstall LTX2.3 VR-Outpaint IC-LoRA](https://huggingface.co/TheBurgstall/VR-360-Outpaint-LTX2.3-IC-LoRA)
as a standard square, circular, equidistant **domemaster**.

## Workflow

```text
[Load Video] → [Rectilinear → Equirect] → VR-Outpaint LoRA
             → [Source Composite] → [Equirect → Domemaster] → save
```

Projection and finishing nodes come from
[ComfyUI-VR-Outpaint-Tools](https://github.com/Burgstall-labs/ComfyUI-VR-Outpaint-Tools).

## Input formats

The node supports three useful input paths:

- **1:1 square hemisphere:** a 180° × 180° equirectangular canvas. Leave
  `input_hfov_deg=180`, `input_vfov_deg=180`, and
  `center_crop_2_1=false`.
- **2:1 full-sphere ERP:** use the entire 360° × 180° panorama. Set
  `input_hfov_deg=360`, `input_vfov_deg=180`, and leave
  `center_crop_2_1=false`.
- **Centered hemisphere from a 2:1 ERP:** enable `center_crop_2_1`. The node
  extracts the centered 1:1 square from the 2:1 input and interprets that crop
  as 180° × 180°. This option overrides the two input-span values.

The center-crop path is useful when the LoRA produces better results on a full
2:1 ERP but only the forward hemisphere is needed for the dome. The crop is
performed before aiming and projection, so yaw or tilt cannot pull content
from the discarded rear half of the ERP.

A warning is logged if the input aspect ratio and selected angular spans do
not agree. The default orientation matches VR-Outpaint-Tools: longitude
increases toward image-right and latitude upward. Leave `mirror_x=false`
unless the target viewer or venue requires an outside-dome convention.

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
| `input_hfov_deg` / `input_vfov_deg` | Input angular span; defaults to 180 / 180 for a 1:1 hemisphere |
| `center_crop_2_1` | Internally crop a 2:1 ERP to its central 1:1, 180° × 180° hemisphere |
| `batch_size` | GPU render chunk size; lower it if a large video runs out of VRAM |
| `mirror_x` | Optional left/right mirror; off is correct for Burgstall VR-Outpaint |

Pixels outside the fisheye circle, and directions outside a partial input
canvas, render black. Keep the equirectangular video as the master and use the
domemaster as the delivery render.

## Memory behavior

All frames share one projection grid. Frames are sampled in configurable
chunks and written directly into the output tensor, avoiding a batch-sized
grid copy and full-batch float32 conversion. Output resolution and the final
ComfyUI image batch still consume VRAM; reduce `batch_size`, `size`, or the
upstream video batch if necessary.

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

The tests verify the center and four dome-rim directions, mirroring, chunked
batches, and the 2:1 center-crop path.

## License

PolyForm Noncommercial License 1.0.0. Noncommercial use is free. Commercial
use requires a separate license; contact **howdy@theaiwrangler.com**.
