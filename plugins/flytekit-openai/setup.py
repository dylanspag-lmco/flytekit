from setuptools import setup

PLUGIN_NAME = "openai"
BATCH_PACKAGE = "openai_batch"
CHATGPT_PACKAGE = "chatgpt"

microlib_name = f"flytekitplugins-{PLUGIN_NAME}"

plugin_requires = ["flytekit>1.10.7", "openai>=1.12.0", "flyteidl>=1.11.0"]

__version__ = "0.0.0+develop"

setup(
    name=microlib_name,
    version=__version__,
    author="flyteorg",
    author_email="admin@flyte.org",
    description="This package holds the openai plugins for flytekit",
    namespace_packages=["flytekitplugins"],
    packages=[
        f"flytekitplugins.{BATCH_PACKAGE}",
        f"flytekitplugins.{CHATGPT_PACKAGE}",
    ],
    install_requires=plugin_requires,
    license="apache2",
    python_requires=">=3.8",
    classifiers=[
        "Intended Audience :: Science/Research",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Scientific/Engineering",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Topic :: Software Development",
        "Topic :: Software Development :: Libraries",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    entry_points={
        "flytekit.plugins": [
            f"{BATCH_PACKAGE}=flytekitplugins.{BATCH_PACKAGE}",
            f"{CHATGPT_PACKAGE}=flytekitplugins.{CHATGPT_PACKAGE}",
        ]
    },
)
