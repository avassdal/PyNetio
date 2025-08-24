"""Exception classes for NETIO device communication errors.

This module defines a hierarchy of exceptions for handling various error
conditions that can occur during communication with NETIO devices.
"""


class NetioException(Exception):
    """Base exception class for all NETIO-related errors.
    
    This is the root exception class from which all other NETIO-specific
    exceptions inherit. Use this for catching any NETIO-related error.
    """


class CommunicationError(NetioException):
    """Exception raised when device communication fails.
    
    This exception is raised for various communication issues including:
    - HTTP errors (non-200 status codes)
    - Network connectivity problems
    - Invalid JSON responses
    - Protocol-level communication failures
    """


class AuthError(NetioException):
    """Exception raised for authentication and authorization errors.
    
    This exception is raised when:
    - No authentication credentials are provided
    - Invalid username or password
    - Insufficient permissions for the requested operation
    - SSL certificate validation failures
    """


class UnknownOutputId(NetioException):
    """Exception raised when referencing an invalid output ID.
    
    This exception is raised when attempting to access or control
    an output that doesn't exist on the device (e.g., requesting
    output 5 on a 4-output device).
    """
