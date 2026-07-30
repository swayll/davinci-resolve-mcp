#!/usr/bin/env python
"""Apply Tilt to V3 clips in specified timelines.

Usage:
  1. Edit the `tilts` dict below — map timeline-name-substring → Tilt value
  2. Run with Resolve API environment variables
"""

import sys
import DaVinciResolveScript as dvr_script

# --- CONFIGURE HERE ---
# Key = substring to match in timeline name (case-insensitive)
# Value = Tilt (Y-position) as a float
tilts = {
    "01 Интро": -363.0,
    "04 Финал": -345.0,
}
# ----------------------


def main():
    resolve = dvr_script.scriptapp("Resolve")
    if not resolve:
        sys.exit("Cannot connect to DaVinci Resolve")

    proj = resolve.GetProjectManager().GetCurrentProject()
    if not proj:
        sys.exit("No project open")

    count = int(proj.GetTimelineCount() or 0)
    if count == 0:
        sys.exit("No timelines in project")

    # Build a lookup: timeline_name → timeline object
    all_tls = {}
    for i in range(1, count + 1):
        tl = proj.GetTimelineByIndex(i)
        all_tls[tl.GetName()] = tl

    applied = []
    skipped = []

    for search, tilt in tilts.items():
        search_lower = search.lower()
        found = None
        for name, tl in all_tls.items():
            if search_lower in name.lower():
                found = tl
                break

        if not found:
            skipped.append((search, "not found"))
            continue

        # Switch to the timeline
        proj.SetCurrentTimeline(found)

        # Get clip on V3
        items = found.GetItemsInTrack("video", 3)
        if not items:
            skipped.append((search, "no clip on V3"))
            continue

        keys = sorted(items.keys())
        item = items[keys[0]]

        # Apply Tilt
        result = item.SetProperty("Tilt", float(tilt))
        if result:
            applied.append((found.GetName(), tilt))
        else:
            skipped.append((search, f"SetProperty returned False (Tilt={tilt})"))

    # Report
    print("=== Applied ===")
    for name, tilt in applied:
        print(f"  ✅ {name} → Tilt {tilt}")

    print("\n=== Skipped ===")
    for search, reason in skipped:
        print(f"  ⚠️  \"{search}\" — {reason}")

    if not skipped:
        print("  (none)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
