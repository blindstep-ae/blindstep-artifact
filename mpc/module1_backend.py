from Compiler.types import sint, Array, MemValue
from Compiler.library import for_range, print_ln, crash, if_

# ==========================================================
# Layer B: MP-SPDZ Ingress + Aggregation Adapter (inside MPC)
# ==========================================================

def load_external_cpsi_shares(N_F, M_MAX=3):
    """
    [REAL CPSI INGRESS]
    Read the two-party secret shares produced by the external CPSI / private
    join backend.

    Expected share-file format:
    For every A[i] (N_F rows in total) the writer emits M_MAX match slots
    followed by one overflow bit:
      for i in N_F:
        for m in M_MAX:
          flag_share   (Player 0/1)
          score_share  (Player 0/1)
        overflow_share (Player 0/1)

    Returns the securely recombined arrays (share0 + share1, performed
    implicitly by sint assignment/addition inside MP-SPDZ).
    """
    cpsi_flags = Array(N_F * M_MAX, sint)
    cpsi_scores = Array(N_F * M_MAX, sint)
    overflow_flags = Array(N_F, sint)
    
    @for_range(N_F)
    def _(i):
        @for_range(M_MAX)
        def _(m):
            idx = i * M_MAX + m
            f_p0 = sint.get_input_from(0)
            f_p1 = sint.get_input_from(1)
            # [BLINDSTEP ARITHMETIZATION] b0 ^ b1 = b0 + b1 - 2*b0*b1
            cpsi_flags[idx] = f_p0 + f_p1 - 2 * f_p0 * f_p1
            
            s_p0 = sint.get_input_from(0)
            s_p1 = sint.get_input_from(1)
            # Scores remain arithmetic.
            cpsi_scores[idx] = s_p0 + s_p1

        ovf_p0 = sint.get_input_from(0)
        ovf_p1 = sint.get_input_from(1)
        # Overflow flags are XOR boolean.
        overflow_flags[i] = ovf_p0 + ovf_p1 - 2 * ovf_p0 * ovf_p1

    return cpsi_flags, cpsi_scores, overflow_flags

# ==========================================================
# Party-0 private A-side input loader (shared by all pipelines)
# ==========================================================

def load_private_inputs(N_F):
    """
    Two-party private A-side input loading (real share files, NOT mock data).

    Consumes the 2*N_F-line A-side prefix that the external writer
    (external_backend/volepsi/frontend/perf.cpp and
    scripts/simulate_cpp_writer.py) emits BEFORE the CPSI slot lines:
      lines [0, N_F)       -> A_scores[i]  (P0 real value, P1 zero-share)
      lines [N_F, 2*N_F)   -> A_valid[i]   (P0 real value, P1 zero-share)

    MUST be called BEFORE load_external_cpsi_shares() so the input stream
    stays aligned with the writer's line order. Single source of truth: this
    replaces the identical per-program copies that used to live in
    blindstep_full*.mpc and baseline_*.mpc.
    """
    A_scores = Array(N_F, sint)
    A_valid  = Array(N_F, sint)

    @for_range(N_F)
    def _(i):
        A_scores[i] = sint.get_input_from(0)
        sint.get_input_from(1)  # consume P1 zero-share for A_scores

    @for_range(N_F)
    def _(i):
        A_valid[i] = sint.get_input_from(0)
        sint.get_input_from(1)  # consume P1 zero-share for A_valid

    return A_scores, A_valid

# ==========================================================
# BlindStep Aggregation Adapter (row-aligned multi-source aggregation layer)
# ==========================================================

def aggregation_layer(cpsi_flags, cpsi_scores, overflow_flags, A_scores, A_valid, N_F, M_MAX=3):
    """
    Consume the M_MAX slot inputs delivered by the external CPSI and sum
    securely across slots in the MPC arithmetic domain.

    Guarantees:
    1. Row alignment is preserved; rows are never collapsed into a
       variable-length set.
    2. Fail-closed defense: if any overflow is detected the protocol is
       deliberately aborted.
    """
    valid_flags = Array(N_F, sint)
    s_A_array   = Array(N_F, sint)
    s_B_array   = Array(N_F, sint)
    
    # Overflow protection: fail-closed audit accumulator
    global_overflow = MemValue(sint(0))

    @for_range(N_F)
    def _(i):
        hit_sum     = MemValue(sint(0))
        b_score_acc = MemValue(sint(0))
        
        global_overflow.write(global_overflow.read() + overflow_flags[i])

        @for_range(M_MAX)
        def _(m):
            idx = i * M_MAX + m
            f = cpsi_flags[idx]
            s = cpsi_scores[idx]
            hit_sum.write(hit_sum.read() + f)
            b_score_acc.write(b_score_acc.read() + f * s)

        # Arithmetic greater-than: a hit sum above 0 marks the row as matched
        matched_i = hit_sum.read() > 0

        # Definition 3.1: v_i = v_i^(A) AND [sum_j f_ij > 0].
        # Restore the A-side validity conjunction (kernel-layer defense).
        # In all current experiments A_valid == 1, so outputs are unchanged.
        valid_flags[i] = A_valid[i] * matched_i
        s_A_array[i]   = A_valid[i] * A_scores[i]
        s_B_array[i]   = b_score_acc.read()

    # Fail-closed audit: abort the protocol if any external overflow occurred,
    # preventing silent forgery. Per Definition 5.2 we must reveal only a single
    # bit ("does not reveal how many rows overflowed"): compare the secret sum to
    # 0 in the secure domain first, then reveal only that comparison bit. The
    # summation is unchanged (sum-then-compare, one comparison; not a per-row OR,
    # which would add N multiplications).
    ov_glob = global_overflow.read() > 0   # secure comparison, result stays a secret bit
    check = ov_glob.reveal()               # reveal only this single bit
    @if_(check > 0)
    def _():
        print_ln("[FATAL] Global overflow triggered during external CPSI! (Hits > M_MAX). Fail-closed activated.")
        crash()

    return valid_flags, s_A_array, s_B_array
