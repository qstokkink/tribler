"""
Child File Descriptors are only supported by Twisted for Linux.
If support is added for other platforms, add them to CHILDFDS_ENABLED.
Possible values are (see platform.system):
    - 'Linux'
    - 'Windows'
    - 'Java'
    - ''
"""

from platform import system

CHILDFDS_ENABLED = system() in ['Linux',]
