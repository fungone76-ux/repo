"""Entry point for Luna RPG v4."""
from __future__ import annotations

import sys

from luna.ui.app import main
from luna.core.debug_tracer import enable_debug

if __name__ == "__main__":
    # V4.2: Command line arguments
    debug_mode = "--debug" in sys.argv
    no_media = "--no-media" in sys.argv
    
    if debug_mode:
        print("🔍 LUNA DEBUG MODE ENABLED")
        print("   Logs will be saved to: logs/luna_debug.log")
        print("   Errors will be saved to: logs/luna_errors.log")
        print()
        enable_debug()
        sys.argv.remove("--debug")
    
    if no_media:
        print("🖼️  MEDIA GENERATION DISABLED")
        print("   Images and videos will NOT be generated")
        print("   Use this for faster testing")
        print()
        sys.argv.remove("--no-media")
    
    # Pass options to main
    sys.exit(main(debug=debug_mode, no_media=no_media))