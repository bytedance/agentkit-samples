from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "check_prime.py"
SPEC = importlib.util.spec_from_file_location("a2a_check_prime", MODULE_PATH)
check_prime_module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(check_prime_module)


@pytest.mark.parametrize(
    ("numbers", "expected"),
    [
        ([], "No prime numbers found."),
        ([0, 1, -7, 9, 12], "No prime numbers found."),
        ([2], "2 are prime numbers."),
        ([2, 3, 4, 5], "2, 3, 5 are prime numbers."),
        (["11", "12", "13"], "11, 13 are prime numbers."),
    ],
)
def test_check_prime_reports_prime_numbers(numbers, expected):
    assert asyncio.run(check_prime_module.check_prime(numbers)) == expected


def test_check_prime_deduplicates_repeated_primes():
    result = asyncio.run(check_prime_module.check_prime([7, "7", 14, 7]))

    assert result == "7 are prime numbers."


def test_check_prime_handles_square_numbers_as_composite():
    result = asyncio.run(check_prime_module.check_prime([25, 29, 49]))

    assert result == "29 are prime numbers."
