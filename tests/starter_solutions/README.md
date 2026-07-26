# Starter verifier reference overlays

These files prove that each owned starter case has at least one correct answer.

The verification script copies a clean starting repository, checks that it fails, applies
one overlay, and checks that it passes. Inspect mounts only the starting repository into an
agent trial. It does not mount this folder.
