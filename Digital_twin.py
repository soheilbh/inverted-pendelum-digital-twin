import pygame
import serial
import numpy as np
import csv
import math
import scipy.integrate as it
import time
import pandas as pd

class DigitalTwin:
    def __init__(self):
        # Initialize Pygame parameters
        self.screen = None
        self.x_pivot_limit = 100
        self.integral_error = 0.0
        # Initialize serial communication parameters
        self.ser = None
        self.device_connected = False
        # State configuration parameters
        self.steps = 0
        self.theta = 0.#np.pi-0.01
        self.theta_dot = 0.
        self.theta_double_dot = 0.
        self.x_pivot = 0
        self.delta_t = 0.005  # Example value, adjust as needed in seconds
        # Model parameters
        self.g = 9.81  # Acceleration due to gravity (m/s^2)
        self.l = 0.8   # Length of the pendulum (m)
        self.c_air = 0.0416  # Air friction coefficient (Matches damping B from paper)
        self.c_c = 0.608e-3  # Coulomb friction coefficient (Matches Tq from paper)
        self.a_m = 2000  # Reduced from 3000 to 30 for more realistic force transfer
        self.future_motor_accelerations = []
        self.future_motor_positions = []
        self.currentmotor_acceleration = 0.
        self.time = 0.
        # Sensor data
        self.sensor_theta = 0
        self.current_sensor_motor_position = 0.
        self.current_action = 0
        # Keyboard action mappings
        _action_durations = [200, 150, 100, 50]  # Durations in milliseconds
        _keys_left = [pygame.K_a, pygame.K_s, pygame.K_d, pygame.K_f]
        _keys_right = [pygame.K_SEMICOLON, pygame.K_l, pygame.K_k , pygame.K_j]
        self.actions = {key: ('left', duration) for key, duration in zip(_keys_left, _action_durations)}
        self.actions.update({key: ('right', duration) for key, duration in zip(_keys_right, _action_durations)})
        self.action_map = [
            ('left', 0),  # No action
            ('left', 50), ('left', 100), ('left', 150), ('left', 200),
            ('right', 50), ('right', 100), ('right', 150), ('right', 200)
        ]
        self.recording = False
        self.writer = None
        self.start_time = 0.
        self.df = None


        self.R = 8.6538       # Ohms
        self.k = 0.0174       # Motor constant
        self.Bv = 5.9751e-7   # Viscous friction (Nms)
        self.J = 8.5075e-7    # Moment of inertia (kg·m²)
        self.L = 0.0238       # Inductance (H)
        self.Tq = 0.6082e-3   # Static friction (Nm)
        self.gear_ratio = 340.0
        self.pulley_radius = 0.01  # meters

        
        # Initialize a pygame window
        self.initialize_pygame_window()

    def initialize_pygame_window(self):
        # Set up the drawing window
        pygame.init()
        self.screen = pygame.display.set_mode([1000, 800])

    def connect_device(self, port='COM3', baudrate=115200):
        # Establish a serial connection for sensor data
        self.ser = serial.Serial(port=port, baudrate=baudrate, timeout=0, writeTimeout=0)
        self.device_connected = True
        print("Connected to: " + self.ser.portstr)

    def read_data(self):
        line = self.ser.readline()
        line = line.decode("utf-8")
        try:
            if len(line) > 2 and line != '-':
                sensor_data = line.split(",")
                if len(sensor_data[0]) > 0 and len(sensor_data[3]) > 0:
                    self.sensor_theta = int(sensor_data[0])
                    self.current_sensor_motor_position = -int(sensor_data[3])
        except Exception as e:
            print(e)
        if self.recording:
            self.writer.writerow([round(time.time() * 1000)-self.start_time, self.sensor_theta, self.current_sensor_motor_position])


    def process_data(self):
        """
        Lab 2: Use the sensor data retured by the function read_data. 
        The sensor data needs to be represented in the virtual model.
        First the data should be scaled and calibrated,
        Secondly noise should be reduced trough a filtering method.
        Return the processed data sush that it can be used in visualization and recording.
        Also, transform the current_sensor_motor_position to be acurate. 
        This means that the encoder value should be scaled to match the displacement in the virtual model.
        """
        self.sensor_theta = 0
        self.current_sensor_motor_position = 0
        
    def start_recording(self, name):
        # If you are working on the bonus assignments then you should also add a columb for actions (and safe those).
        self.recording = True
        self.file = open('{}.csv'.format(name), 'w', newline='')  
        self.writer = csv.writer(self.file)
        self.start_time = round(time.time() * 1000)
        self.writer.writerow(["time", "theta", "x_pivot"])

    def stop_recording(self):
        self.recording = False
        self.file.close()
    
    def load_recording(self, name):
        self.df = pd.read_csv('{}.csv'.format(name))
        print("recording is loaded")
    
    def recorded_step(self,i):
        a = self.df["time"].pop(i)
        b = self.df["theta"].pop(i)
        c = self.df["x_pivot"].pop(i)  
        return a, b, c

    def perform_action(self, direction, duration):
        print(f"🎮 PERFORM ACTION: direction={direction}, duration={duration}")
        # Send the command to the device.
        if self.device_connected:
            if direction == 'left':
                d = -duration
            else:
                d = duration
            self.ser.write(str(d).encode())
        if duration > 0:
            self.update_motor_accelerations(direction, duration/1000)

    # # COMPLETE REALISTIC MOTOR MODEL IMPLEMENTATION:
    # def update_motor_accelerations(self, direction, duration):
    #     if direction == 'left':
    #         direction = -1
    #     else:
    #         direction = 1

    #     # Check if the motor should be blocked at the limit
    #     if (self.x_pivot == self.x_pivot_limit and direction > 0) or \
    #     (self.x_pivot == -self.x_pivot_limit and direction < 0):
    #         print(f"🚨 BLOCKED MOVE: x_pivot={self.x_pivot}, direction={direction}")
    #         return  # Stop movement at the boundary

    #     # Convert duration to voltage with stronger scaling
    #     V = direction * (duration/100.0) * 24.0  # Doubled the voltage effect

    #     # Initialize lists
    #     self.future_motor_accelerations = []
    #     self.future_motor_positions = []
    #     current_position = self.x_pivot
    #     current_velocity = 0

    #     # Scale factor to make movement more visible
    #     movement_scale = 100.0  # Adjust this to get visible movement

    #     for t in np.arange(0.0, duration+self.delta_t, self.delta_t):
    #         # Convert linear velocity to angular velocity (scaled)
    #         omega = current_velocity * self.gear_ratio / (self.pulley_radius * movement_scale)

    #         # Calculate back EMF (reduced effect)
    #         V_bemf = self.k * omega * 0.1  # Reduced back EMF effect

    #         # Calculate current with minimum threshold
    #         I = max((V - V_bemf) / self.R, 0.1)  # Ensure some minimum current

    #         # Calculate torques (scaled up)
    #         T_motor = self.k * I * movement_scale
    #         T_viscous = self.Bv * omega * 0.1  # Reduced viscous friction
    #         T_coulomb = self.Tq * np.sign(omega) if abs(omega) > 1e-6 else 0
    #         T_net = T_motor - T_viscous - T_coulomb

    #         # Calculate acceleration (scaled)
    #         alpha = T_net / (self.J * 0.1)  # Reduced inertia effect
    #         linear_accel = alpha * self.pulley_radius / (self.gear_ratio * movement_scale)

    #         # Add boundary checks
    #         if (current_position >= self.x_pivot_limit and direction > 0) or \
    #            (current_position <= -self.x_pivot_limit and direction < 0):
    #             linear_accel = 0

    #         # Update states
    #         self.future_motor_accelerations.append(linear_accel)
    #         current_velocity += linear_accel * self.delta_t
    #         current_position += current_velocity * self.delta_t
    #         self.future_motor_positions.append(current_position)

    #      # Add debug print
    #     print(f"Generated accelerations: {self.future_motor_accelerations[:5]}...")
    #     print(f"Generated positions: {self.future_motor_positions[:5]}...")

        # Add debug print
    # L298 + DC MOTOR REALISTIC IMPLEMENTATION:
    def update_motor_accelerations(self, direction, duration):
        # Match hardware direction
        if direction == 'left':
            direction = 1
        else:
            direction = -1

        # Check limits
        if (self.x_pivot == self.x_pivot_limit and direction > 0) or \
        (self.x_pivot == -self.x_pivot_limit and direction < 0):
            return

        # Motor parameters (L298 + DC motor)
        V_supply = 12.0  # Supply voltage
        duty_cycle = min(duration/200.0, 1.0)  # PWM duty cycle
        V_motor = direction * duty_cycle * V_supply  # Effective motor voltage
        
        # Initialize lists
        self.future_motor_accelerations = []
        self.future_motor_positions = []
        current_position = self.x_pivot
        current_velocity = 0
        current_current = 0  # Motor current
        
        # Simulation time steps
        for t in np.arange(0.0, duration+self.delta_t, self.delta_t):
            # Convert linear velocity to angular velocity
            omega = current_velocity * self.gear_ratio / self.pulley_radius
            
            # Calculate back EMF
            V_bemf = self.k * omega  # Reduced back EMF effect
            
            # Calculate motor current (using L and R)
            dI_dt = (V_motor - V_bemf - self.R * current_current) / self.L
            current_current += dI_dt * self.delta_t
            current_current = np.clip(current_current, -2.0, 2.0)  # Current limit
            
            # Calculate motor torque with reduced effect
            T_motor = self.k * current_current  # Reduced motor torque
            T_viscous = self.Bv * omega
            T_coulomb = self.Tq * np.sign(omega) if abs(omega) > 1e-6 else 0
            T_net = T_motor - T_viscous - T_coulomb
            
            # Convert torque to linear force through gear ratio and pulley
            F_linear = T_net * self.gear_ratio / self.pulley_radius
            
            # Calculate linear acceleration (F = ma)
            linear_accel = F_linear / 1.0  # Increased cart mass to 1.0 kg for more inertia
            linear_accel *= 0.001  # Reduced scale factor for more realistic visualization
            
            # Add boundary checks
            if (current_position >= self.x_pivot_limit and direction > 0) or \
               (current_position <= -self.x_pivot_limit and direction < 0):
                linear_accel = 0
                current_velocity = 0
            
            # Update states with damping
            self.future_motor_accelerations.append(linear_accel)
            current_velocity = current_velocity * 0.99 + linear_accel * self.delta_t  # Added velocity damping
            current_position += current_velocity * self.delta_t
            self.future_motor_positions.append(current_position)
        
        # Debug prints
        print(f"Motor voltage: {V_motor:.2f}V")
        print(f"Initial current: {current_current:.2f}A")
        print(f"Initial acceleration: {self.future_motor_accelerations[0]:.3f} m/s²")
        print(f"Position change: {self.future_motor_positions[-1] - self.x_pivot:.3f} m") 



    # def update_motor_accelerations(self, direction, duration):
        
    #     # Your current implementation remains here
    #     if direction == 'left':
    #         direction = -1
    #     else:
    #         direction = 1

    #     # Check if the motor should be blocked at the limit
    #     if (self.x_pivot == self.x_pivot_limit and direction > 0) or \
    #     (self.x_pivot == -self.x_pivot_limit and direction < 0):
    #         print(f"🚨 BLOCKED MOVE: x_pivot={self.x_pivot}, direction={direction}")
    #         return  # Stop movement at the boundary

    #     a_m_1 = 0.05
    #     a_m_2 = 0.05
    #     t1 = duration/4
    #     t2_d = duration/4
    #     t2 = duration - t2_d

    #     for t in np.arange(0.0, duration+self.delta_t, self.delta_t):
    #         if self.x_pivot == self.x_pivot_limit and direction > 0:
    #             c = 0  # Stop adding force when stuck at the right limit
    #         elif self.x_pivot == -self.x_pivot_limit and direction < 0:
    #             c = 0  # Stop adding force when stuck at the left limit
    #         if t <= t1:
    #             c = -4*direction*a_m_1/(t1*t1) * t * (t-t1)
    #         elif t < t2 and t > t1:
    #             c = 0 
    #         elif t >= t2:
    #             c = 4*direction*a_m_2/(t2_d*t2_d) * (t-t2) * (t-duration)
            
    #         self.future_motor_accelerations.append(c)
        
    #     _velocity = it.cumulative_trapezoid(self.future_motor_accelerations, initial=0)
    #     self.future_motor_positions = list(it.cumulative_trapezoid(_velocity, initial=0))
    
    
    def get_theta_double_dot(self, theta, theta_dot, motor_force):
        """
        Calculate the angular acceleration (second derivative of theta) for the pendulum.
        
        Parameters:
        - theta: Current angle of the pendulum (radians)
        - theta_dot: Current angular velocity of the pendulum (radians/s)
        
        Returns:
        - Angular acceleration (radians/s^2)
        """
        # Gravitational torque component
        torque_gravity = -(self.g / self.l) * np.sin(theta)
        
        # Air friction (proportional to velocity)
        torque_air_friction = -self.c_air * theta_dot
        
        # Coulomb friction (constant magnitude, opposing the motion)
        if abs(theta_dot) > 1e-6:  # Avoid division by zero
            torque_coulomb_friction = -self.c_c * np.sign(theta_dot)
        else:
            # When angular velocity is very close to zero, avoid applying Coulomb friction
            # This prevents the pendulum from getting stuck artificially
            torque_coulomb_friction = 0
        
        # Motor effect: Key change - when the cart accelerates left (negative acceleration),
        # the pendulum should initially swing right (positive torque)
        # We negate the motor acceleration to get this correct behavior

        # Motor effect through gear ratio and pulley
        if (self.x_pivot == -self.x_pivot_limit and motor_force < 0) or \
        (self.x_pivot == self.x_pivot_limit and motor_force > 0):
            print(f"🚨 BLOCKED MOTOR FORCE at x_pivot={self.x_pivot}, motor_force={motor_force}")
            torque_motor = 0
        else:
            # Convert linear force to torque through pendulum geometry
            torque_motor = (-self.a_m * motor_force / self.l) * np.cos(theta)
            # print(f"✅ MOTOR FORCE APPLIED: motor_force={motor_force}, torque_motor={torque_motor}")

        # torque_motor = (-self.a_m * self.currentmotor_acceleration / self.l) * np.cos(theta)
        
        # Sum all torques and calculate angular acceleration
        angular_acceleration = torque_gravity + torque_air_friction + torque_coulomb_friction + torque_motor
        
        return angular_acceleration
  
    def step(self):
        # print(f"STEP: x_pivot={self.x_pivot}, Acceleration={self.currentmotor_acceleration}, Limit={self.x_pivot_limit}")
        # print(f"📌 BEFORE STEP: x_pivot={self.x_pivot}, Future_Positions={self.future_motor_positions}")
        # Get the predicted motor acceleration for the next step and the shift in x_pivot
        self.check_prediction_lists()
        self.currentmotor_acceleration = self.future_motor_accelerations.pop(0)

        # self.stabilize_inverted_pendulum()

        # Prevent motor from applying force if stuck at boundary BEFORE updating `x_pivot`
        if self.x_pivot == -self.x_pivot_limit and self.currentmotor_acceleration < 0:
            self.currentmotor_acceleration = 0  # Stop leftward force
        if self.x_pivot == self.x_pivot_limit and self.currentmotor_acceleration > 0:
            self.currentmotor_acceleration = 0  # Stop rightward force

        # Calculate the new position shift based on motor action
        new_x_pivot = self.x_pivot + self.future_motor_positions.pop(0) / 3

        # Apply limit using self.x_pivot_limit
        if new_x_pivot < -self.x_pivot_limit:
            self.x_pivot = -self.x_pivot_limit
        elif new_x_pivot > self.x_pivot_limit:
            self.x_pivot = self.x_pivot_limit
            
        else:
            self.x_pivot = new_x_pivot


        # print(f"📌 AFTER STEP: x_pivot={self.x_pivot}, Applied_Position_Change={new_x_pivot}")

        # Update the system state based on the action and model dynamics
        self.theta_double_dot = self.get_theta_double_dot(self.theta, self.theta_dot, self.currentmotor_acceleration)
        self.theta += self.theta_dot * self.delta_t
        self.theta_dot += self.theta_double_dot * self.delta_t
        self.time += self.delta_t
        self.steps += 1

        return self.theta, self.theta_dot, self.x_pivot
        

    def draw_line_and_circles(self, colour, start_pos, end_pos, line_width=5, circle_radius=9):
        pygame.draw.line(self.screen, colour, start_pos, end_pos, line_width)
        pygame.draw.circle(self.screen, colour, start_pos, circle_radius)
        pygame.draw.circle(self.screen, colour, end_pos, circle_radius)

    def draw_pendulum(self, colour ,x, y, x_pivot):
        self.draw_line_and_circles(colour, [x_pivot+500, 400], [y+x_pivot+500, x+400])
        
    def render(self, theta, x_pivot):
        self.screen.fill((255, 255, 255))
        # Drawing length of the pendulum
        l = 100
        self.draw_pendulum((0,0,0),math.cos(theta)*l,math.sin(theta)*l,x_pivot)
        # Draw black line and circles for horizontal axis
        self.draw_line_and_circles((0, 0, 0), [400, 400], [600, 400])
        pygame.display.flip()

    def check_prediction_lists(self):
        if len(self.future_motor_accelerations) == 0:
            self.future_motor_accelerations = [0]
        if len(self.future_motor_positions) == 0:
            self.future_motor_positions = [0]

    # def stabilize_inverted_pendulum(self):
    #     """
    #     Simulates key presses to move the motor and keep the pendulum upright.
    #     Uses PID control to determine movement direction and selects predefined movement durations.
    #     """

    #     # Define PID Controller parameters (tune these for better performance)
    #     Kp = 10.0  # Proportional gain (how strongly it reacts to tilt)
    #     Ki = 0.5   # Integral gain (helps correct small steady errors)
    #     Kd = 3.0   # Derivative gain (reduces oscillations)

    #     # Error: How far the pendulum is from vertical (0 rad)
    #     error = self.theta - np.pi  # Target is now π (not 0)

    #     # Compute the derivative of the error (change in theta over time)
    #     d_error = self.theta_dot  # Theta_dot is how fast the pendulum is tilting

    #     # Integrate the error over time (accumulate corrections)
    #     self.integral_error += error * self.delta_t  # Accumulate small corrections

    #     # Compute control signal (motor movement needed)
    #     control_signal = - (Kp * error + Ki * self.integral_error + Kd * d_error)

    #     # Determine direction based on control signal
    #     if control_signal > 0:
    #         direction = 'right'
    #         actions_list = [(key, duration) for key, (dir, duration) in self.actions.items() if dir == 'right']
    #     else:
    #         direction = 'left'
    #         actions_list = [(key, duration) for key, (dir, duration) in self.actions.items() if dir == 'left']

    #     # Choose the appropriate action based on how much correction is needed
    #     abs_control_signal = abs(control_signal)
        
    #     if abs_control_signal > 1.5:
    #         selected_action = actions_list[0]  # Largest movement
    #     elif abs_control_signal > 1.0:
    #         selected_action = actions_list[1]
    #     elif abs_control_signal > 0.5:
    #         selected_action = actions_list[2]
    #     else:
    #         selected_action = actions_list[3]  # Smallest movement

    #     key, duration = selected_action

    #     # Simulate key press by calling perform_action()
    #     self.perform_action(direction, duration)


