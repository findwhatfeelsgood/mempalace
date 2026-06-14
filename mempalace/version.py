"""Single source of truth for the MemPalace package version."""

# Upstream baseline — kept exactly aligned so upstream version/README
# consistency checks stay green and the fork diff stays clean.
__version__ = "3.3.0"

# FWFG fork build marker — identifies this as the FWFG fork (vs a stale
# upstream/global install). Surfaced by `mempalace doctor`.
FWFG_BUILD = "fwfg.20260614"
FWFG_VERSION = f"{__version__}+{FWFG_BUILD}"
