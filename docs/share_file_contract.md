# Share File Contract (Input-Px-0 Specification)

**Status:** Hypothetical Reference / Concept Standard.

This specification documents the physical handshake protocol currently utilized by BlindStep's MP-SPDZ `module1_backend.py` to ingest external Private Join variables over disk.

## Physical Format

The payload takes the form of line-separated integer arrays injected into MP-SPDZ's primary parallel read pipes: `Player-Data/Input-P0-0` (Player 0's shares) and `Player-Data/Input-P1-0` (Player 1's shares).

For every `$A[i]$` (sequencing through fully from `0` to `N_F - 1`):
1. For `m` from `0` to `M_MAX - 1` ($M\_MAX$ total repeating blocks per candidate):
   - `flag_share`: The additive shadow of the hit validity (1 for hit, 0 for empty/padded).
   - `score_share`: The additive shadow of the associated $B\_score_{j}$ matching this hash locus.
2. After $M\_MAX$ elements:
   - `overflow_share`: The additive shadow of an overflow bit (1 if total backend collisions for $A[i]$ exceeded the allocated $M\_MAX$ slot tolerance, zero otherwise).

## Runtime Safety (Fail-Closed)
At the commencement of `aggregation_layer()`, MP-SPDZ resolves every line utilizing:
`real_value = sint.get_input_from(0) + sint.get_input_from(1)`

All extracted `overflow_shares` are locally audited as `global_overflow = sum(overflow_flags[i])`. 
If `global_overflow.reveal() > 0`, MP-SPDZ immediately aborts via `crash()`, rejecting to produce a fragmented Top-K query trace based on silent truncation.
