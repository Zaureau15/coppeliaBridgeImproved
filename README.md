This code is designed to interface threaded Python code with CoppeliaSim using a common thread for all ZMQ requests to CoppeliaSim. Any code that sends messages to CoppeliaSim or gets information from CoppeliaSim should use this bridge if your Python code is threaded.

Initialize the bridge and start the simulation at the beginning of your code as follows:

```python
# Create bridge using official CoppeliaSim Python API
bridge = CoppeliaSimBridge(host='localhost', port=23000)
bridge.start()
time.sleep(1.0)  # Let bridge initialize
```

Many common functions from the CoppeliaSim API are wrapped in this code.  Without the bridge, your code would look like this

```python
left_motor = sim.getObject('leftMotor')
velocity = 0.5
sim.setJointTargetVelocity(left_motor, velocity)
```

The same process using the bridge would look like this:

```python
left_motor = bridge.get_object_handle('leftMotor')
velocity = 0.5
bridge.set_joint_target_velocity(left_motor, velocity)
```

Finally, stop the simulation at the end of your script:

```python
# Stop the simulation
bridge.stop_simulation()
```
