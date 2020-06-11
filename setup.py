"""Helpful nixpkgs PR bot with an improved Genuine People Personality"""

from setuptools import setup

setup(
    name="marvin",
    # No point in cutting releases here.
    version="rolling",
    description="Helpful nixpkgs PR bot with an improved Genuine People Personality",
    author="Timo Kaufmann",
    packages=["marvin"],
    install_requires=["aiohttp", "gidgethub"],
    entry_points={"console_scripts": ["marvin=marvin.__main__:main"]},
)
