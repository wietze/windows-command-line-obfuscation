import setuptools

description_short = "Project for identifying executables that have command-line options that can be obfuscated, possibly bypassing detection rules."
with open("README.md", "r", encoding="utf-8") as fh:
    description_long = fh.read()

setuptools.setup(
    name="analyse_obfuscation",
    version="1.1.0",
    author="@Wietze",
    description=description_short,
    long_description=description_long,
    long_description_content_type="text/markdown",
    url="https://github.com/wietze/windows-command-line-obfuscation",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU Affero General Public License v3",
        "Operating System :: Microsoft :: Windows",
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'Intended Audience :: System Administrators',
        'Topic :: Security',
        'Topic :: Internet :: Log Analysis',
        'Environment :: Console',
    ],
    entry_points={
        'console_scripts': [
            'analyse_obfuscation = analyse_obfuscation.run:parse_arguments'
        ],
    },
    install_requires=['tqdm', 'colorama', 'terminaltables']
)
