import threading
import queue
import time
from typing import Any, Optional, Callable, Literal, TypeAlias
from collections.abc import Iterable

# Ignoring type for RemoteAPIClient because stubs are not available
from coppeliasim_zmqremoteapi_client import RemoteAPIClient  # type: ignore

VisionSensorReading: TypeAlias = (
    tuple[int, list[float], *tuple[list[float], ...]] | Literal[-1]
)

VisionSensorImage: TypeAlias = tuple[bytes, list[int]]

ProximitySensorReading: TypeAlias = tuple[
    int, float, list[float], int, list[float]
]


class ZMQRequest:
    """Request object for synchronous communication."""

    def __init__(
        self,
        function: Callable[..., Any],
        args: Any,
        kwargs: Any,
    ):
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.response_queue: queue.Queue[Any] = queue.Queue()

    def wait_for_response(self, timeout: float = 5.0) -> Optional[Any]:
        try:
            return self.response_queue.get(timeout=timeout)
        except queue.Empty:
            return None


class CoppeliaSimBridge:
    """
    Thread-safe bridge using CoppeliaSim's official Python API.
    Much simpler - no manual CBOR encoding or message formatting!
    """

    def __init__(self, host: str = "localhost", port: int = 23000):
        self.host = host
        self.port = port
        self.running = False
        self.thread = None
        self.request_queue: queue.Queue[ZMQRequest] = queue.Queue()

        # CoppeliaSim API objects (owned by bridge thread only!)
        self.client: Any = None
        self.sim: Any = None

    def start(self):
        """Start the bridge thread."""
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        print(f"[CoppeliaSimBridge] Started on thread {self.thread.ident}")

    def _run(self):
        """Main bridge loop."""
        thread_id = threading.current_thread().ident
        print(
            f"[CoppeliaSimBridge] Initializing CoppeliaSim API "
            f"on thread {thread_id}"
        )

        # Initialize CoppeliaSim client in this thread
        self.client = RemoteAPIClient(self.host, self.port)
        self.sim = self.client.require("sim")

        print(
            f"[CoppeliaSimBridge] Connected to CoppeliaSim "
            f"at {self.host}:{self.port}"
        )

        while self.running:
            try:
                # Get request from queue
                request = self.request_queue.get(timeout=0.1)

                # Execute the function
                try:
                    result = request.function(*request.args, **request.kwargs)
                    request.response_queue.put(result)
                except Exception as e:
                    request.response_queue.put({"error": str(e)})

            except queue.Empty:
                continue
            except Exception as e:
                print(f"[CoppeliaSimBridge] Error: {e}")

    def stop(self):
        """Stop the bridge."""
        print("[CoppeliaSimBridge] Stopping...")
        self.running = False
        if self.thread:
            self.thread.join()
        print("[CoppeliaSimBridge] Stopped")

    def _call_sync(
        self,
        function: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Optional[Any]:
        """
        Thread-safe synchronous call to CoppeliaSim.
        Can be called from any thread.
        """
        request = ZMQRequest(function, args, kwargs)
        self.request_queue.put(request)
        return request.wait_for_response()

    # Public API - Thread-safe wrappers around CoppeliaSim functions

    def get_object_handle(self, path: str) -> Optional[int | Literal[-1]]:
        """Get object handle by path/name."""
        return self._call_sync(lambda: self.sim.getObject(path))

    def get_object_position(
        self, object_handle: int, relative_to: int = -1
    ) -> Optional[list[float]]:
        """Get object position [x, y, z]."""
        return self._call_sync(
            lambda: self.sim.getObjectPosition(object_handle, relative_to)
        )

    def set_object_position(
        self, object_handle: int, position: list[float], relative_to: int = -1
    ) -> None:
        """Set object position."""
        self._call_sync(
            lambda: self.sim.setObjectPosition(
                object_handle, relative_to, position
            )
        )

    def get_object_orientation(
        self, object_handle: int, relative_to: int = -1
    ) -> Optional[list[float]]:
        """Get object orientation [alpha, beta, gamma] (Euler angles)."""
        return self._call_sync(
            lambda: self.sim.getObjectOrientation(object_handle, relative_to)
        )

    def set_object_orientation(
        self,
        object_handle: int,
        orientation: list[float],
        relative_to: int = -1,
    ) -> None:
        """Set object orientation [alpha, beta, gamma] (Euler angles)."""
        self._call_sync(
            lambda: self.sim.setObjectOrientation(
                object_handle, relative_to, orientation
            )
        )

    def get_vision_sensor_img(
        self,
        sensor_handle: int,
        options: int = 0,
        rgbaCutOff: float = 0.0,
        pos: list[int] = [0, 0],
        size: list[int] = [0, 0],
    ) -> Optional[VisionSensorImage]:
        """
        Get vision sensor image.
        Consider using alongside unpack_uint8_table to get int values.
        Returns: (image_data, resolution)
        """
        return self._call_sync(
            lambda: self.sim.getVisionSensorImg(
                sensor_handle, options, rgbaCutOff, pos, size
            )
        )

    def get_vision_sensor_img_multiple(
        self,
        sensor_handles: Iterable[int],
        options: int = 0,
        rgbaCutOff: float = 0.0,
        pos: list[int] = [0, 0],
        size: list[int] = [0, 0],
    ) -> list[Optional[VisionSensorImage]]:
        """
        Get images from multiple vision sensors. Faster than calling
        `get_vision_sensor_img` multiple times.

        Returns
        -------
        list[Optional[VisionSensorImage]]
            A list of `(image_data, resolution)` tuples, one per sensor.
        """
        images: list[Optional[VisionSensorImage]] = []

        for handle in sensor_handles:
            image = self._call_sync(
                lambda: self.sim.getVisionSensorImg(
                    handle, options, rgbaCutOff, pos, size
                )
            )
            images.append(image)

        return images

    def unpack_uint8_table(
        self, data: bytes, startUint8Index: int = 0, uint8Count: int = 0
    ) -> Optional[list[int]]:
        """
        Unpacks a string (or part of it) into an array of uint8 numbers.
        """
        return self._call_sync(
            lambda: self.sim.unpackUInt8Table(
                data, startUint8Index, uint8Count
            )
        )

    def read_vision_sensor(
        self, sensor_handle: int
    ) -> Optional[VisionSensorReading]:
        """
        Read the state of a vision sensor.

        Returns
        -------
        -1
            Returned if no data is available (e.g., if the simulation
            has not yet started).

        tuple
            Tuple containing:

            detection_state: int
                Detection state (0 or 1).

            aux_values: list[float]
                List of 15 auxiliary values: the minimum of [intensity
                red green blue depth], the maximum of [intensity red
                green blue depth], and the average of [intensity red
                green blue depth]

            additional_packets: list[float]
                One or more additional auxiliary value packets.
        """
        return self._call_sync(
            lambda: self.sim.readVisionSensor(sensor_handle)
        )

    def read_vision_sensors_multiple(
        self, sensor_handles: Iterable[int]
    ) -> list[Optional[VisionSensorReading]]:
        """
        Read the state of multiple vision sensors. Faster than calling
        `read_vision_sensor` multiple times.

        Returns
        -------
        list[Optional[VisionSensorReading]]
            A list of readings, one for each sensor.
        """
        readings: list[Optional[VisionSensorReading]] = []

        for handle in sensor_handles:
            reading = self._call_sync(
                lambda: self.sim.readVisionSensor(handle)
            )

            if reading == -1:
                readings.append(None)
            else:
                readings.append(reading)

        return readings

    def read_proximity_sensor(
        self, sensor_handle: int
    ) -> Optional[ProximitySensorReading]:
        """
        Read the state of a proximity sensor.
        Use this when you are sure you have only one sensor.
        It is faster than calling multiple `read_proximity_sensor`s.

        Returns
        -------
        tuple[int, float, list[float], int, list[float]]
            A tuple containing:

            res : int
                Detection state (0 or 1).

            dist : float
                Distance to the detected point.

            point : list[float]
                Relative coordinates of the detected point as [x, y, z].

            obj : int
                Handle of the detected object.

            n : list[float]
                Normal vector of the detected surface (normalized),
                relative to the sensor reference frame.
        """
        return self._call_sync(
            lambda: self.sim.readProximitySensor(sensor_handle)
        )

    def read_proximity_sensors_multiple(
        self, sensor_handles: Iterable[int]
    ) -> list[Optional[ProximitySensorReading]]:
        """
        Read the state of multiple proximity sensors. Faster than
        calling `read_proximity_sensor` multiple times.

        Returns
        -------
        list[Optional[ProximitySensorReading]]
            A list of proximity sensor readings, one for each sensor.
        """
        readings: list[Optional[ProximitySensorReading]] = []

        for handle in sensor_handles:
            reading = self._call_sync(
                lambda: self.sim.readProximitySensor(handle)
            )
            readings.append(reading)

        return readings

    def get_joint_position(self, joint_handle: int) -> Optional[float]:
        """Get joint position (angle in radians)."""
        return self._call_sync(lambda: self.sim.getJointPosition(joint_handle))

    def set_joint_target_velocity(
        self, joint_handle: int, velocity: float
    ) -> None:
        """Set joint target velocity."""
        self._call_sync(
            lambda: self.sim.setJointTargetVelocity(joint_handle, velocity)
        )

    def set_joint_target_position(
        self, joint_handle: int, position: float
    ) -> None:
        """Set joint target position."""
        self._call_sync(
            lambda: self.sim.setJointTargetPosition(joint_handle, position)
        )

    def start_simulation(self) -> None:
        """Start the simulation."""
        self._call_sync(lambda: self.sim.startSimulation())

    def stop_simulation(self) -> None:
        """Stop the simulation."""
        self._call_sync(lambda: self.sim.stopSimulation())

    def get_simulation_time(self) -> Optional[float]:
        """Get current simulation time."""
        return self._call_sync(lambda: self.sim.getSimulationTime())

    def step(self) -> None:
        """Step the simulation."""
        self._call_sync(lambda: self.sim.step())

    def set_stepping(self, enable: bool) -> Optional[int]:
        """
        Turn stepping mode on/off.
        Returns: bool of previous level of thread interruption. When 0,
        thread interruption was not enabled previously
        """
        return self._call_sync(lambda: self.sim.setStepping(enable))
