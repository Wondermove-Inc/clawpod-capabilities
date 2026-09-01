from setuptools import setup, find_namespace_packages
setup(name="cli-anything-clawpod-cloud-webhooks", version="0.2.7", packages=find_namespace_packages(include=["cli_anything.*"]), install_requires=["click>=8.1", "cryptography>=42"], entry_points={"console_scripts":["cli-anything-clawpod-cloud-webhooks=cli_anything.clawpod_cloud_webhooks.clawpod_cloud_webhooks_cli:main"]})
