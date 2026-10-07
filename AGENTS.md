# Market Report Safety Rules

- Never publish an infographic before validating its source report.
- Never combine different report time slots.
- Never invent market numbers.
- Never use decorative financial charts or gauges.
- Never mark an artifact complete before readback.
- Never publish to GitHub before Google Docs validation.
- Never mark Portal as published before public readback.
- Treat each report time slot as an independent artifact.
- A generated image is DRAFT until post-generation validation passes.
- Validation failure must block publication.

Use the immutable source lock, machine-readable stage results, and identity-bound readback evidence in `docs/INFOGRAPHIC_VALIDATOR.md`. `--dry-run` publication commands never connect to or write production services. Do not treat fixture evidence as external publication evidence.
