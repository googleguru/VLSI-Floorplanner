from setuptools import setup, find_packages

setup(
    name="ca-floorplanner",
    version="1.0.0",
    description="Rule-Based Cellular Automata Floorplanner for VLSI Physical Design",
    author="R.Pavithra Guru",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.9",
    install_requires=open("requirements.txt").read().splitlines(),
    entry_points={
        "console_scripts": [
            "ca-floorplan=eval.experiment_driver:cli",
        ]
    },
)
