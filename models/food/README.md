# Food Model V1

`best.pt` is intentionally not stored in Git.  The V1 demonstration model is
YOLO11s, seed 3407, with a 640-pixel input and a default confidence threshold
of `0.25`.

The weights and `backend/scripts/food_model/classes.yaml` are an inseparable
pair.  Before using a downloaded weight, verify both hashes from
`model_manifest.json`:

```text
best.pt       19,194,771 bytes  680accafc8c22854b37e959106c37a44b3e8c42b4d260d7f3c4681021c2a31cd
classes.yaml         640 bytes  8bd06c89afe18fbb6bf7d64d44b51f84f8199a80678e63123f35c09fd6c9913b
```

When the `food-model-v1.0` prerelease is available, download and verify the
weight from the repository root:

```powershell
.\scripts\download_food_model.ps1
```

The script writes only `models/food/best.pt`; it never replaces the tracked
class map.  For native runs, set `FOOD_PROVIDER=yolo`, point
`FOOD_MODEL_PATH` at this file, set `FOOD_CLASSES_PATH` to the tracked class
map, and keep `FOOD_CONF_THRESHOLD=0.25`.  Docker mounts this directory at
`/models/food` read-only.

This is a 12-class demonstration detector, not a general food recognizer.
Its results require user confirmation before recipe generation; recipe and
nutrition output are not medical or nutrition advice.
