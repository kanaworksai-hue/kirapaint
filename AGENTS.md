# KiraPaint — instructions for AI agents

The human only says something like *"make my model painterly and sparkly"*, *「KiraPaintでキラキラにして」* or
*「用 KiraPaint 把模型做成碎钻 2.5D」*. You do everything: install, apply, show a preview.
Do not ask the human to click anything in Blender.

KiraPaint works on any model (glTF/GLB, FBX, OBJ, .blend) whose materials use a Principled BSDF — that covers
almost every downloaded, scanned or AI-generated model. Objects without a material get a default one.
It never replaces materials; `--remove` puts everything back.

## 1. Find Blender
- macOS: `/Applications/Blender*.app/Contents/MacOS/Blender`
- Windows: `C:\Program Files\Blender Foundation\Blender */blender.exe`
- Linux: `blender` on PATH
Needs **5.0+**. Folder names don't always show the version, so ask each one and pick the newest:
```bash
for b in /Applications/Blender*.app/Contents/MacOS/Blender; do echo "$("$b" --version | head -1) | $b"; done
```

## 2. Install (once)
Get the latest `kirapaint-<version>.zip` from https://github.com/kanaworksai-hue/kirapaint/releases
and `agent/kirapaint_agent.py` from the repository:
```bash
git clone --depth 1 https://github.com/kanaworksai-hue/kirapaint.git
gh release download -R kanaworksai-hue/kirapaint -p 'kirapaint-*.zip'          # with gh
# or without gh:
curl -sL "$(curl -s https://api.github.com/repos/kanaworksai-hue/kirapaint/releases/latest \
  | grep -o 'https://[^"]*kirapaint-[^"]*\.zip' | head -1)" -o kirapaint.zip
```
Then:
```bash
<blender> -b --python agent/kirapaint_agent.py -- --install kirapaint-<version>.zip
```
Never add `--factory-startup` to the install command — the install is saved into the user's preferences and
factory startup would overwrite them. The script refuses in that case.
Success = last line starts with `KIRAPAINT OK`.

## 3. Apply

### a) A model file (glb / gltf / fbx / obj), Blender closed
```bash
<blender> -b --python agent/kirapaint_agent.py -- --model duck.glb --preset KIRA \
    --save duck_kira.blend --render preview.png
```
A camera is added and pointed at the model.

### b) A .blend file, Blender closed
```bash
<blender> -b scene.blend --python agent/kirapaint_agent.py -- --preset KIRA \
    --save scene_kira.blend --render preview.png
```
Save to a new file unless the human asked to overwrite. Show them `preview.png`.

### c) A running Blender (e.g. through a Blender MCP / Python console)
```python
import bpy
bpy.ops.kirapaint.make_kira(preset="KIRA", target="SELECTED_OR_ALL")
bpy.ops.kirapaint.make_kira(sparkle=1.0, iridescence=1.0)          # later tweak: keeps everything else
bpy.context.scene.kirapaint.paint = 0.0                              # plain render again (animatable)
bpy.ops.kirapaint.remove()
```
`target`: `SELECTED_OR_ALL` (default), `SELECTED`, `ALL`. `doodles`: `AUTO` / `ON` / `OFF`. `steam`: True/False.

## 4. Turning the human's words into options

**No style given** ("make it sparkly / painterly"): `--preset KIRA`. Add `--steam` for hot food.
Omit `--preset` on later tweaks: the current look is kept and only what you pass changes.

| They say | preset |
|---|---|
| sparkly, crushed diamond, キラキラ, 碎钻, 亮晶晶, glitter (default) | `KIRA` |
| soft, oil paint, gentle, やわらか, 油画, 柔和 | `SOFT` |
| bold, comic, thick lines, くっきり, 粗线, 漫画感 | `INK` |
| dreamy, rainbow, holographic, ゆめかわ, 梦幻, 彩虹 | `DREAMY` |

| They say | option |
|---|---|
| more / less sparkle, 閃光, 闪光 | `--sparkle 1.0` / `--sparkle 0.3` |
| bigger / smaller brush strokes, 笔触大/小 | `--brush 7` / `--brush 3` |
| more broken / chunkier facets, 碎一点 | `--facets 1.6` (smaller) / `--facets 0.7` (bigger) |
| less painted, closer to the original | `--stroke 0.4` |
| more rainbow / pink-cyan sheen, 虹色 | `--iridescence 1.0` |
| less shiny, matte | `--gloss 0.3` |
| glow, bloom, 发光 | `--bloom 0.7` |
| thicker / no outline | `--outline 2` / `--no-outline` |
| no doodles, no stars around it | `--doodles off` |
| steam, 热气, 湯気 | `--steam` |
| background colors: night / purple → `NIGHT`, stars / navy → `STARRY`, pink / sakura → `SAKURA`, polka dots / strawberry milk → `POLKA`, mint / green → `MINT`, sky / blue → `SODA`, yellow / lemon / cream → `LEMON`, peach / pastel → `PEACH`, sunset / orange → `SUNSET`, grey / studio / neutral → `STUDIO` | `--background NAME` |
| keep my background / world | `--background KEEP` |
| realistic → painted reveal animation | `--reveal 24` |
| rotate / turntable / 回転 / 旋转 N degrees | `--turntable 60` |

## 5. Fine-tuning in a running Blender
Settings live on `bpy.context.scene.kirapaint`: `paint stroke facets gloss iridescence brush sparkle bloom outline background`.
Setting them updates every KiraPaint material, the compositor and the glint lights at once.
After moving the camera, re-aim the lights and redraw the doodles:
```python
bpy.ops.kirapaint.relight(); bpy.ops.kirapaint.doodles()
```

## Getting the best result (do this, the human won't ask)
1. Render a preview and look at it before reporting back. Use `--preview-size 50` for quick looks.
2. Light-colored models (cream, white) blow out more easily: if the preview is too white, lower `--sparkle`
   and `--gloss` a little. Dark models (bronze, wood, pumpkins) take `--iridescence 1.0` well.
3. If the human's own camera cuts the model off, add `--frame-camera` (a separate camera; theirs is untouched).
4. Offer two or three variations (presets or backgrounds) as small previews and let the human pick in one word.
   Food and cute props look great on `SAKURA`, `POLKA`, `MINT`, `LEMON`; glossy dark objects on `NIGHT` or `STARRY`.
5. Report what you changed in one sentence, with the preview.

## Notes
- Needs EEVEE (set automatically). The compositor does the painting: renders show the full look; in the
  viewport, set the Compositor option of the viewport shading to "Always" to preview it.
- Materials without a Principled BSDF (e.g. MochiToon toon materials, pure emission) are skipped and reported.
- Sister add-on: [MochiToon](https://github.com/kanaworksai-hue/mochitoon) (cute manga toon). Pick MochiToon for
  "manga / comic / toon / かわいく", KiraPaint for "painterly / sparkly / 2.5D / キラキラ". Use one per object.
