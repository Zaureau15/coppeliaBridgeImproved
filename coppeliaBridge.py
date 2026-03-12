import threading
import queue
import time
from typing import Any, Optional, Callable, Literal
from collections.abc import Iterable

# Ignoring type for RemoteAPIClient because stubs are not available
from coppeliasim_zmqremoteapi_client import RemoteAPIClient  # type: ignore


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

    getObject = get_object_handle

    def get_object_position(
        self, object_handle: int, relative_to: int = -1
    ) -> Optional[list[float]]:
        """Get object position [x, y, z]."""
        return self._call_sync(
            lambda: self.sim.getObjectPosition(object_handle, relative_to)
        )

    getObjectPosition = get_object_position

    def set_object_position(
        self, object_handle: int, position: list[float], relative_to: int = -1
    ) -> None:
        """Set object position."""
        self._call_sync(
            lambda: self.sim.setObjectPosition(
                object_handle, relative_to, position
            )
        )

    setObjectPosition = set_object_position

    def get_object_orientation(
        self, object_handle: int, relative_to: int = -1
    ) -> Optional[list[float]]:
        """Get object orientation [alpha, beta, gamma] (Euler angles)."""
        return self._call_sync(
            lambda: self.sim.getObjectOrientation(object_handle, relative_to)
        )

    getObjectOrientation = get_object_orientation

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

    setObjectOrientation = set_object_orientation

    def get_vision_sensor_img(
        self,
        sensor_handle: int,
        options: int = 0,
        rgbaCutOff: float = 0.0,
        pos: list[int] = [0, 0],
        size: list[int] = [0, 0],
    ) -> Optional[tuple[bytes, list[int]]]:
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

    getVisionSensorImg = get_vision_sensor_img

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

    unpackUInt8Table = unpack_uint8_table

    def read_vision_sensor(
        self, sensor_handle: int
    ) -> Optional[
        tuple[int, list[float], *tuple[list[float], ...]] | Literal[-1]
    ]:
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

    readVisionSensor = read_vision_sensor

    def read_proximity_sensor(
        self, sensor_handle: int
    ) -> Optional[tuple[int, float, list[float], int, list[float]]]:
        """
        Read the state of a proximity sensor.

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

    readProximitySensor = read_proximity_sensor

    def get_joint_position(self, joint_handle: int) -> Optional[float]:
        """Get joint position (angle in radians)."""
        return self._call_sync(lambda: self.sim.getJointPosition(joint_handle))

    getJointPosition = get_joint_position

    def set_joint_target_velocity(
        self, joint_handle: int, velocity: float
    ) -> None:
        """Set joint target velocity."""
        self._call_sync(
            lambda: self.sim.setJointTargetVelocity(joint_handle, velocity)
        )

    setJointTargetVelocity = set_joint_target_velocity

    def set_joint_target_position(
        self, joint_handle: int, position: float
    ) -> None:
        """Set joint target position."""
        self._call_sync(
            lambda: self.sim.setJointTargetPosition(joint_handle, position)
        )

    setJointTargetPosition = set_joint_target_position

    def start_simulation(self) -> None:
        """Start the simulation."""
        self._call_sync(lambda: self.sim.startSimulation())

    startSimulation = start_simulation

    def stop_simulation(self) -> None:
        """Stop the simulation."""
        self._call_sync(lambda: self.sim.stopSimulation())

    stopSimulation = stop_simulation

    def get_simulation_time(self) -> Optional[float]:
        """Get current simulation time."""
        return self._call_sync(lambda: self.sim.getSimulationTime())

    getSimulationTime = get_simulation_time

    def step(self) -> None:
        """Step the simulation."""
        self._call_sync(lambda: self.sim.step())

    step = step

    def set_stepping(self, enable: bool) -> Optional[int]:
        """
        Turn stepping mode on/off.
        Returns: bool of previous level of thread interruption. When 0,
        thread interruption was not enabled previously
        """
        return self._call_sync(lambda: self.sim.setStepping(enable))

    setStepping = set_stepping


if __name__ == "__main__":
    bridge = CoppeliaSimBridge()
    bridge.start()
    bridge.stop_simulation()
    time.sleep(0.1)
    bridge.start_simulation()
    time.sleep(0.1)

    handle = bridge.getObject("/proximitySensor")
    if not handle or handle < 0:
        print("No sensor found")
        exit(1)
    content = bridge.read_proximity_sensor(handle)

    print("handle:", handle, type(handle))
    print("content:", content, type(content))
    if not isinstance(content, Iterable):
        print("Content is not iterable")
        exit(1)
    print("elem types:", [type(x) for x in content])
