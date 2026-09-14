from Compiler.types import sint, Array, MemValue
from Compiler.library import for_range

# =============== Core Encodings ===============

def get_tuple_shifts(N_F, SCORE_BITS):
    import math
    requested_tie_bits = 2 * math.ceil(math.log2(max(N_F, 2))) + 20
    max_tie_bits = 63 - SCORE_BITS - 1
    
    if requested_tie_bits > max_tie_bits:
        raise ValueError(f"Requested TIE_BITS={requested_tie_bits} exceeds backend-safe max={max_tie_bits}")
    
    TIE_BITS = requested_tie_bits
    PACKED_BITS = 1 + SCORE_BITS + TIE_BITS
    
    SCORE_SHIFT = TIE_BITS
    VALID_SHIFT = TIE_BITS + SCORE_BITS
    MAX_TIE = (2 ** TIE_BITS) - 1
    return TIE_BITS, PACKED_BITS, SCORE_SHIFT, VALID_SHIFT, MAX_TIE

def encode_tuple(valid, score, tie, VALID_SHIFT, SCORE_SHIFT, MAX_TIE):
    inverted_tie = MAX_TIE - tie
    return valid * (2 ** VALID_SHIFT) + score * (2 ** SCORE_SHIFT) + inverted_tie

def decode_tuple(packed_clear, VALID_SHIFT, SCORE_SHIFT, SCORE_BITS, TIE_BITS, MAX_TIE):
    valid = (packed_clear >> VALID_SHIFT) & 1
    score = (packed_clear >> SCORE_SHIFT) & ((1 << SCORE_BITS) - 1)
    inverted_tie = packed_clear & ((1 << TIE_BITS) - 1)
    tie = MAX_TIE - inverted_tie
    return valid, score, tie

# =============== Secure Primitives ===============

def secure_eq(a, b):
    """
    Secure equality test: sint -> sint in {0, 1}.
    """
    diff = a - b
    return diff == 0

# =============== Composition & Packing ===============

def compose_scores(valid_flags, s_A_array, s_B_array, N_F):
    """S_total = S_A + S_B."""
    total_scores = Array(N_F, sint)
    @for_range(N_F)
    def _(i):
        total_scores[i] = s_A_array[i] + s_B_array[i]
    return total_scores

def prepare_candidate_table(valid_flags, total_scores, N_F, VALID_SHIFT, SCORE_SHIFT, MAX_TIE):
    """Pack (valid, score, tie)."""
    table = Array(N_F, sint)
    TIE_BITS = SCORE_SHIFT
    
    # Vectorized random bit generation to prevent WAN communication hangs
    tie_vals = Array(N_F, sint)
    tie_vals.assign(sint.get_random_int(TIE_BITS, size=N_F))
    
    from Compiler.library import for_range_opt
    @for_range_opt(N_F)
    def _(i):
        tie_val = tie_vals[i]
        table[i] = encode_tuple(valid_flags[i], total_scores[i], tie_val, VALID_SHIFT, SCORE_SHIFT, MAX_TIE)
    return table
