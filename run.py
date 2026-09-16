#!/usr/bin/env python3
"""Convenience launcher, so `python run.py` works as well as `python -m tapo_weather`."""

from tapo_weather.__main__ import run

if __name__ == "__main__":
    run()
