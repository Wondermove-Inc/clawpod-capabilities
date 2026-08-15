# Safety

S0 observes. S1 performs reversible named actions. S2 requires exact preview and scoped confirmation. S3 external commitments require fresh explicit approval. S4 destructive or privileged actions require fresh explicit approval and recovery disclosure. CAPTCHA and human verification always stop. Image or coordinate approval binds screenshot hash, display geometry, target and revision. Unknown dialogs fail closed.


Display metrics are immutable. Resolution, geometry, DPI, scale, X resources, X settings, and desktop/X session lifecycle are not approval-gated mutations; they are structurally unsupported and must be rejected before dispatch. A supported backend operation must preserve its pre-operation geometry/DPI snapshot or fail closed with `DESKTOP_STATE_CHANGED`.
