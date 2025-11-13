"""
Setup script for Archon Shared Models package.
"""

from setuptools import find_packages, setup

setup(
    name="archon-shared-models",
    version="1.0.0",
    description="Shared Pydantic models for Archon services",
    author="Archon Team",
    python_requires=">=3.11",
    packages=find_packages(),
    install_requires=[
        "pydantic>=2.5.0",
        "typing-extensions>=4.8.0",
    ],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
