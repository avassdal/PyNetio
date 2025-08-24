"""Device abstraction layer for NETIO power management devices.

This module provides abstract base classes and concrete implementations
for communicating with NETIO devices via their JSON API.
"""

import dataclasses
import json
from abc import abstractmethod, ABC
from enum import IntEnum
from typing import Dict, List, Optional, Union, Any, Iterable

import requests

from Netio.exceptions import CommunicationError, AuthError, UnknownOutputId


class Device(ABC):
    """Abstract base class for NETIO device communication.
    
    This class defines the interface for interacting with NETIO power management
    devices. Concrete implementations must provide the _get_outputs and _set_outputs
    methods to handle device-specific communication.
    
    Attributes:
        DeviceName: Human-readable name of the device.
        SerialNumber: Unique serial number of the device.
        NumOutputs: Number of controllable outputs on the device.
    """

    _write_access = False

    class ACTION(IntEnum):
        """Enumeration of possible output actions.
        
        Values correspond to the NETIO M2M API protocol specification.
        See: https://www.netio-products.com/files/NETIO-M2M-API-Protocol-JSON.pdf
        """

        OFF = 0
        ON = 1
        SHORT_OFF = 2
        SHORT_ON = 3
        TOGGLE = 4
        NOCHANGE = 5
        IGNORED = 6

    DeviceName: str = ""
    SerialNumber: str = "Unknown"
    NumOutputs: int = 0

    @dataclasses.dataclass
    class OUTPUT:
        ID: int
        """Output ID"""

        Name: str
        """Output name"""

        State: int
        """Output state"""

        Action: "Device.ACTION"
        """"""

        Delay: int
        """[ms] Output delay for short On/Off"""

        Current: float
        """[mA] Electric current for the output"""

        PowerFactor: float
        """[-] TPF True Power Factor for the output"""

        Phase: float
        """[°] Phase for the specific power output"""

        Energy: float
        """[Wh] Counter of Energy consumed per output (resettable)"""

        Energy_NR: float
        """[Wh] Not Resettable counter of output consumed Energy"""

        ReverseEnergy: float
        """[Wh] Counter of Energy produced per output (resettable)"""

        ReverseEnergy_NR: float
        """[Wh] Not Resettable counter of Reversed (produced) Energy"""

        Load: float
        """[W] Instantaneous load (power) for the specific power output"""

    @abstractmethod
    def __init__(self, *args, **kwargs):
        """Initialize the device connection.
        
        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
        """
        pass

    @abstractmethod
    def _get_outputs(self) -> List[OUTPUT]:
        """Retrieve current state of all device outputs.
        
        Returns:
            List of OUTPUT dataclass instances representing current output states.
            
        Raises:
            CommunicationError: If device communication fails.
            AuthError: If authentication is invalid or insufficient.
        """

    @abstractmethod
    def _set_outputs(self, actions: Dict[int, ACTION]) -> None:
        """Set the state of multiple device outputs.
        
        Args:
            actions: Dictionary mapping output IDs to desired actions.
            
        Raises:
            CommunicationError: If device communication fails.
            AuthError: If authentication is invalid or insufficient.
        """

    def get_outputs(self) -> List[OUTPUT]:
        """Get the current state of all device outputs.
        
        Returns:
            List of OUTPUT instances containing current state information
            for all outputs on the device.
        """
        return self._get_outputs()

    def get_outputs_filtered(self, ids: Iterable[int]) -> Iterable[OUTPUT]:
        """Get outputs filtered by specified IDs.
        
        Args:
            ids: Iterable of output IDs to retrieve.
            
        Yields:
            OUTPUT instances for each requested output ID.
            
        Raises:
            UnknownOutputId: If any requested output ID is invalid.
        """
        outputs = self.get_outputs()
        for i in ids:
            try:
                yield next(filter(lambda output: output.ID == i, outputs))
            except StopIteration:
                raise UnknownOutputId("Invalid output ID")

    def get_output(self, id: int) -> OUTPUT:
        """Get the current state of a specific output.
        
        Args:
            id: The output ID to retrieve (typically 1-based).
            
        Returns:
            OUTPUT instance containing the current state of the specified output.
            
        Raises:
            UnknownOutputId: If the output ID is invalid or doesn't exist.
        """
        outputs = self.get_outputs()
        try:
            return next(filter(lambda output: output.ID == id, outputs))
        except StopIteration:
            raise UnknownOutputId("Invalid output ID")

    def set_outputs(self, actions: Dict[int, ACTION]) -> None:
        """Set the state of multiple outputs simultaneously.
        
        Args:
            actions: Dictionary mapping output IDs to desired ACTION values.
                    Example: {1: Device.ACTION.ON, 2: Device.ACTION.OFF}
                    
        Raises:
            AuthError: If the device connection lacks write permissions.
            CommunicationError: If device communication fails.
        """
        # TODO verify if socket id's are in range
        if self._write_access:
            self._set_outputs(actions)
        else:
            raise AuthError("cannot write, without write access")

    def set_output(self, id: int, action: ACTION) -> None:
        """Set the state of a single output.
        
        Args:
            id: The output ID to control (typically 1-based).
            action: The ACTION to perform on the output.
            
        Raises:
            AuthError: If the device connection lacks write permissions.
            CommunicationError: If device communication fails.
        """
        self.set_outputs({id: action})

    def __repr__(self) -> str:
        """Return a string representation of the device.
        
        Returns:
            String in format '<Netio DeviceName [SerialNumber]>'.
        """
        return f"<Netio {self.DeviceName} [{self.SerialNumber}]>"


class JsonDevice(Device):
    """Concrete implementation for NETIO devices using JSON API.
    
    This class implements the Device interface for NETIO devices that support
    the JSON M2M API protocol over HTTP/HTTPS.
    """
    
    def __init__(
        self, url: str, auth_r: Optional[tuple] = None, auth_rw: Optional[tuple] = None, 
        verify: Optional[Union[bool, str]] = None, skip_init: bool = False, timeout: Optional[float] = None
    ) -> None:
        """Initialize connection to a NETIO device via JSON API.
        
        Args:
            url: Full URL to the device's JSON API endpoint.
            auth_r: Tuple of (username, password) for read-only access.
            auth_rw: Tuple of (username, password) for read-write access.
            verify: SSL certificate verification. True to verify, False to disable,
                   or string path to CA bundle file.
            skip_init: If True, skip device initialization during construction.
            timeout: Request timeout in seconds.
            
        Raises:
            AuthError: If no authentication credentials are provided.
        """
        self._url = url
        self._verify = verify
        self._timeout = timeout

        # read-write can do read, so we don't need read-only permission
        if auth_rw:
            self._user = auth_rw[0]
            self._pass = auth_rw[1]
            self._write_access = True
        elif auth_r:
            self._user = auth_r[0]
            self._pass = auth_r[1]
        else:
            raise AuthError("No auth provided.")

        if not skip_init:
            self.init()

    def init(self) -> None:
        """Initialize device by fetching basic device information.
        
        Retrieves and stores device name, serial number, and output count
        from the device's Agent information.
        
        Raises:
            CommunicationError: If device communication fails.
            AuthError: If authentication is invalid.
        """
        # request information about the Device
        r_json = self._get()

        self.NumOutputs = r_json["Agent"]["NumOutputs"]
        self.DeviceName = r_json["Agent"]["DeviceName"]
        self.SerialNumber = r_json["Agent"]["SerialNumber"]

    def get_device_info(self) -> Dict[str, Any]:
        """Get comprehensive device information excluding output states.
        
        Returns:
            Dictionary containing device information such as Agent details,
            GlobalMeasure data, etc., but without Outputs section.
            
        Raises:
            CommunicationError: If device communication fails.
            AuthError: If authentication is invalid.
        """
        r_json = self._get()
        r_json.pop("Outputs")
        return r_json

    @staticmethod
    def _parse_response(response: requests.Response) -> dict:
        """Parse HTTP response according to NETIO M2M API protocol.
        
        Args:
            response: HTTP response object from requests library.
            
        Returns:
            Parsed JSON response as dictionary.
            
        Raises:
            CommunicationError: For HTTP errors or invalid JSON responses.
            AuthError: For authentication or permission errors.
            
        References:
            https://www.netio-products.com/files/NETIO-M2M-API-Protocol-JSON.pdf
        """

        if response.status_code == 400:
            raise CommunicationError("Control command syntax error")

        if response.status_code == 401:
            raise AuthError("Invalid Username or Password")

        if response.status_code == 403:
            raise AuthError("Insufficient permissions to write")

        if not response.ok:
            raise CommunicationError(f"Communication with device failed: HTTP {response.status_code} - {response.reason}")

        try:
            rj = response.json()
        except ValueError:
            raise CommunicationError("Response does not contain valid json")

        return rj

    def _post(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """Send POST request to device with JSON payload.
        
        Args:
            body: Dictionary to send as JSON payload.
            
        Returns:
            Parsed JSON response from device.
            
        Raises:
            AuthError: If SSL certificate is invalid or authentication fails.
            CommunicationError: If request fails or response is invalid.
        """
        try:
            response = requests.post(
                self._url,
                data=json.dumps(body),
                auth=requests.auth.HTTPBasicAuth(self._user, self._pass),
                verify=self._verify,
                timeout=self._timeout,
            )
        except requests.exceptions.SSLError:
            raise AuthError("Invalid certificate")

        return self._parse_response(response)

    def _get(self) -> Dict[str, Any]:
        """Send GET request to device to retrieve current state.
        
        Returns:
            Parsed JSON response containing device state and output information.
            
        Raises:
            AuthError: If SSL certificate is invalid or authentication fails.
            CommunicationError: If request fails or response is invalid.
        """
        try:
            response = requests.get(
                self._url,
                auth=requests.auth.HTTPBasicAuth(self._user, self._pass),
                verify=self._verify,
                timeout=self._timeout,
            )
        except requests.exceptions.SSLError:
            raise AuthError("Invalid certificate")

        return self._parse_response(response)

    def _get_outputs(self) -> List[Device.OUTPUT]:
        """Retrieve current state of all device outputs.
        
        Sends a GET request to the device and parses the output states
        according to the NETIO M2M API specification.
        
        Returns:
            List of OUTPUT dataclass instances with current state information.
            
        Raises:
            CommunicationError: If device communication fails.
            AuthError: If authentication is invalid.
        """

        r_json = self._get()

        outputs = list()

        for output in r_json.get("Outputs"):
            state = self.OUTPUT(
                ID=output.get("ID", None),
                Name=output.get("Name", None),
                State=output.get("State", None),
                Action=self.ACTION(output.get("Action")),
                Delay=output.get("Delay", None),
                Current=output.get("Current", None),
                PowerFactor=output.get("PowerFactor", None),
                Phase=output.get("Phase", None),
                Energy=output.get("Energy", None),
                Energy_NR=output.get("Energy_NR", None),
                ReverseEnergy=output.get("ReverseEnergy", None),
                ReverseEnergy_NR=output.get("ReverseEnergy_NR", None),
                Load=output.get("Load", None),
            )
            outputs.append(state)
        return outputs

    def _set_outputs(self, actions: Dict[int, "Device.ACTION"]) -> Dict[str, Any]:
        """Set the state of multiple device outputs.
        
        Args:
            actions: Dictionary mapping output IDs to ACTION enum values.
            
        Returns:
            Parsed JSON response from the device.
            
        Raises:
            CommunicationError: If device communication fails.
            AuthError: If authentication is invalid or insufficient permissions.
        """
        outputs = []
        for id, action in actions.items():
            outputs.append({"ID": id, "Action": action})

        body = {"Outputs": outputs}

        return self._post(body)

        # TODO verify response action
