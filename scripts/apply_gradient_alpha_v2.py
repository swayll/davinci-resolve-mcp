#!/usr/bin/env python
"""Create Gradient-alpha mask on V2 clip, connect as EffectMask, set Channel=Luminance."""

import os
import sys
import DaVinciResolveScript as dvr_script

SETTINGS_PATH = os.path.join(os.path.dirname(__file__), "Gradient-Alpha.setting")


def main():
    resolve = dvr_script.scriptapp("Resolve")
    if not resolve:
        sys.exit("Cannot connect to DaVinci Resolve")

    proj = resolve.GetProjectManager().GetCurrentProject()
    timeline = proj.GetCurrentTimeline()
    if not timeline:
        sys.exit("No current timeline")

    items = timeline.GetItemsInTrack("video", 2)
    if not items:
        sys.exit("No items on video track 2")

    keys = sorted(items.keys())
    item = items[keys[0]]
    print(f"Found clip on V2: {item.GetName()}")

    # Remove any existing Fusion comps for a clean start
    comp_count = int(item.GetFusionCompCount() or 0)
    if comp_count > 0:
        comp_names = item.GetFusionCompNameList() or []
        for name in comp_names:
            item.DeleteFusionCompByName(name)
            print(f"Deleted existing Fusion comp: {name}")

    # Create fresh Fusion composition
    comp = item.AddFusionComp()
    if not comp:
        sys.exit("Failed to create Fusion comp on timeline item")
    print("Fusion composition created")

    comp.Lock()
    try:
        # Add Background tool from .settings
        bg = comp.AddTool("Background")
        if not bg:
            sys.exit("Failed to add Background tool")
        bg.LoadSettings(SETTINGS_PATH)
        print("Background tool created with gradient settings")

        # Find MediaIn1 and connect EffectMask
        media_in = comp.FindTool("MediaIn1")
        if not media_in:
            sys.exit("MediaIn1 not found in composition")
        media_in.ConnectInput("EffectMask", bg)
        print("EffectMask connected: MediaIn1.EffectMask <- Background1")

        # Set Channel to Luminance
        media_in.SetInput("Channel", "Luminance")
        print("MediaIn1 Channel set to Luminance")
    finally:
        comp.Unlock()

    print("Done — gradient-alpha mask with Luminance channel applied to V2 clip")


if __name__ == "__main__":
    main()
