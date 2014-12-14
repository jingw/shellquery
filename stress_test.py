#!/usr/bin/env python
import random
import string
import subprocess
import sys
import tempfile
import time

import shellquery


def run_test(rows, max_columns, max_col_length, trials):
    print(
        "rows={}, max_columns={}, max_col_length={}".format(
            rows, max_columns, max_col_length
        )
    )

    def rand_col():
        return "".join(
            random.choice(string.ascii_letters) for _ in range(max_col_length)
        )

    def rand_row():
        cols = random.randint(0, max_columns)
        return [rand_col() for _ in range(cols)]

    for i in range(trials):
        with tempfile.NamedTemporaryFile() as f:
            for r in range(rows):
                f.write(" ".join(rand_row()).encode("utf-8"))
                f.write(b"\n")
            f.flush()
            start = time.time()
            out = subprocess.check_output(
                [
                    sys.executable,
                    shellquery.__file__,
                    'SELECT COUNT(*) FROM "{}"'.format(f.name),
                ]
            )
            elapsed = time.time() - start
            assert int(out) == rows
            print("    {:.2f} seconds".format(elapsed))


if __name__ == "__main__":
    run_test(100, 10, 100, 3)
    run_test(10000, 100, 10, 3)
