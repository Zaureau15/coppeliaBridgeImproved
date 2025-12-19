import threading
import time
import queue
from typing import Any, Optional, Callable
from coppeliasim_zmqremoteapi_client import RemoteAPIClient


class ZMQRequest:
    """Request object for synchronous communication."""

    def __init__(self, function: Callable, args: tuple, kwargs: dict):
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.response_queue = queue.Queue()

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
        self.request_queue = queue.Queue()

        # CoppeliaSim API objects (owned by bridge thread only!)
        self.client = None
        self.sim = None

    def start(self):
        """Start the bridge thread."""
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        print(f"[CoppeliaSimBridge] Started on thread {self.thread.ident}")

    def _run(self):
        """Main bridge loop."""
        thread_id = threading.current_thread().ident
        print(f"[CoppeliaSimBridge] Initializing CoppeliaSim API on thread {thread_id}")

        # Initialize CoppeliaSim client in this thread
        self.client = RemoteAPIClient(self.host, self.port)
        self.sim = self.client.require("sim")

        print(
            f"[CoppeliaSimBridge] Connected to CoppeliaSim at {self.host}:{self.port}"
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

    def _call_sync(self, function: Callable, *args, **kwargs) -> Any:
        """
        Thread-safe synchronous call to CoppeliaSim.
        Can be called from any thread.
        """
        request = ZMQRequest(function, args, kwargs)
        self.request_queue.put(request)
        return request.wait_for_response()

    # Public API - Thread-safe wrappers around CoppeliaSim functions

    def get_object_handle(self, path: str) -> Optional[int]:
        """Get object handle by path/name."""
        return self._call_sync(lambda: self.sim.getObject(path))

    def get_object_position(
        self, object_handle: int, relative_to: int = -1
    ) -> Optional[list]:
        """Get object position [x, y, z]."""
        return self._call_sync(
            lambda: self.sim.getObjectPosition(object_handle, relative_to)
        )

    def set_object_position(
        self, object_handle: int, position: list, relative_to: int = -1
    ):
        """Set object position."""
        return self._call_sync(
            lambda: self.sim.setObjectPosition(object_handle, relative_to, position)
        )

    def get_object_orientation(
        self, object_handle: int, relative_to: int = -1
    ) -> Optional[list]:
        """Get object orientation [alpha, beta, gamma] (Euler angles)."""
        return self._call_sync(
            lambda: self.sim.getObjectOrientation(object_handle, relative_to)
        )

    def get_vision_sensor_img(
        self, sensor_handle: int, options: int = 0
    ) -> Optional[tuple]:
        """
        Get vision sensor image.
        Returns: (image_data, resolution)
        """
        return self._call_sync(
            lambda: self.sim.getVisionSensorImg(sensor_handle, options)
        )

    def read_vision_sensor(self, sensor_handle: int):
        return self._call_sync(lambda: self.sim.readVisionSensor(sensor_handle))

    def get_joint_position(self, joint_handle: int) -> Optional[float]:
        """Get joint position (angle in radians)."""
        return self._call_sync(lambda: self.sim.getJointPosition(joint_handle))

    def set_joint_target_velocity(self, joint_handle: int, velocity: float):
        """Set joint target velocity."""
        return self._call_sync(
            lambda: self.sim.setJointTargetVelocity(joint_handle, velocity)
        )

    def set_joint_target_position(self, joint_handle: int, position: float):
        """Set joint target position."""
        return self._call_sync(
            lambda: self.sim.setJointTargetPosition(joint_handle, position)
        )

    def start_simulation(self):
        """Start the simulation."""
        return self._call_sync(lambda: self.sim.startSimulation())

    def stop_simulation(self):
        """Stop the simulation."""
        return self._call_sync(lambda: self.sim.stopSimulation())

    def get_simulation_time(self) -> float:
        """Get current simulation time."""
        return self._call_sync(lambda: self.sim.getSimulationTime())
