
def binary_rank(vectors):
    """
    Calculate the exact rank of binary vectors over GF(2).

    Each vector is an iterable of 0/1 values.
    Gaussian elimination uses XOR instead of floating-point arithmetic.
    """
    rows = [list(map(int, vector)) for vector in vectors]

    if not rows:
        return 0

    width = len(rows[0])

    if any(len(row) != width for row in rows):
        raise ValueError("All vectors must have the same length")

    if any(value not in (0, 1) for row in rows for value in row):
        raise ValueError("Vectors must contain only 0 and 1")

    rank = 0

    for column in range(width):
        pivot = next(
            (
                row_index
                for row_index in range(rank, len(rows))
                if rows[row_index][column] == 1
            ),
            None,
        )

        if pivot is None:
            continue

        rows[rank], rows[pivot] = rows[pivot], rows[rank]

        for row_index in range(len(rows)):
            if row_index != rank and rows[row_index][column] == 1:
                rows[row_index] = [
                    left ^ right
                    for left, right in zip(rows[row_index], rows[rank])
                ]

        rank += 1

        if rank == len(rows):
            break

    return rank
