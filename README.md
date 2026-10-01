# Gartner Hover Card

Rest the mouse on a node in Nuke's Node Graph and a small card shows what you
need to know about it, without opening anything.

- **Warnings first:** errors, missing file on the current frame, disabled
- **Per node type:**
  - Read: colorspace, frame range on disk, file
  - Write: output, folder, file type, colorspace
  - Merge: operation, and which nodes feed A and B
  - Group / gizmo: nodes inside, gizmo file
- **Image info:** resolution, frames, layers, bbox (when bigger than the
  format), premult, cook time (when profiling is on), downstream node count
- **Changed:** every knob you changed from its default, with its value
- **Pipes:** rest on a pipe to see where it comes from, goes to, and which input
- **Backdrops:** rest on the title strip to see the label and nodes inside

Nothing in your script is changed. It's one Python file with no dependencies.

## Install

1. Copy `gartner_hover_card.py` into your `.nuke` folder
   (`C:\Users\<you>\.nuke` on Windows, `~/.nuke` on macOS and Linux),
   or any folder on your `NUKE_PATH`.
2. Add this line to the `menu.py` in that folder (create the file if it
   doesn't exist):

   ```python
   import gartner_hover_card
   ```

3. Restart Nuke.

Turn it on or off from **Gartner > Hover Card On - Off**.

## Settings

Edit the `Settings` class at the top of `gartner_hover_card.py`:

| Setting | Default | What it does |
|---|---|---|
| `delay` | `0.5` | Seconds the mouse rests on a node before the card appears |
| `accent` | `#f5c518` | Accent colour of the card |
| `card_max_changed` | `8` | How many changed knobs to list |
| `pipe_info` | `True` | Show cards for pipes too |
| `view_scale` | `1.0` | Only change this if the card picks the wrong node |

## Compatibility

Tested with Nuke 16 on Windows. Older Nuke versions (PySide2) may need small
adjustments, especially if the card appears for the wrong node.
