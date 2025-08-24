"""NETIO power management device library.

This package provides Python interfaces for controlling NETIO power management
devices via their JSON M2M API. The main entry point is the Netio class,
which is an alias for JsonDevice.

Example:
    >>> from Netio import Netio
    >>> device = Netio('http://netio.local/netio.json', 
    ...                auth_rw=('admin', 'password'))
    >>> device.set_output(1, device.ACTION.ON)
"""

from Netio.Device import JsonDevice as Netio  # Default device

__all__ = ['Netio']
