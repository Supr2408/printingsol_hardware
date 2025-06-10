import RPi.GPIO as GPIO
import time

# Pin Configuration
# Motor 1
DIR1 = 20
STEP1 = 21
SLEEP1 = 16

# Motor 2
DIR2 = 26
STEP2 = 19
SLEEP2 = 13

# Motor 3
DIR3 = 6
STEP3 = 5
SLEEP3 = 4

# Constants
STEP_PER_REV = 200  # Steps per revolution (typical for 1.8 degreee stepper motor)
LEAD = 8.0  # Lead screw lead in mm (8mm per revolution)
STEPS_PER_ROTATION = STEP_PER_REV  # Steps for one full rotation

# GPIO Setup
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup([DIR1, STEP1, SLEEP1, DIR2, STEP2, SLEEP2, DIR3, STEP3, SLEEP3], GPIO.OUT)

# Sleep Control Functions
def enable_motors_1_2():
    GPIO.output(SLEEP1, GPIO.HIGH)
    GPIO.output(SLEEP2, GPIO.HIGH)
    GPIO.output(SLEEP3, GPIO.LOW)

def enable_motor3():
    GPIO.output(SLEEP1, GPIO.LOW)
    GPIO.output(SLEEP2, GPIO.LOW)
    GPIO.output(SLEEP3, GPIO.HIGH)

def disable_all_motors():
    GPIO.output(SLEEP1, GPIO.LOW)
    GPIO.output(SLEEP2, GPIO.LOW)
    GPIO.output(SLEEP3, GPIO.LOW)

def move_motor(motor: str, direction: bool, speed: float, rotations: int):
    """
    Move selected motor(s) for given rotations.
    :param motor: '1_2' for motors 1 and 2, '3' for motor 3
    :param direction: True for forward, False for backward
    :param speed: Speed in RPM
    :param rotations: Number of full rotations
    """
    steps = int(rotations * STEPS_PER_ROTATION)
    delay = 60.0 / (speed * STEP_PER_REV) / 2  # Calculate delay for speed
    
    if motor == '1_2':
        enable_motors_1_2()
        GPIO.output(DIR1, GPIO.HIGH if direction else GPIO.LOW)
        GPIO.output(DIR2, GPIO.HIGH if direction else GPIO.LOW)
        for step in range(steps):
            GPIO.output(STEP1, GPIO.HIGH)
            GPIO.output(STEP2, GPIO.HIGH)
            time.sleep(delay)
            GPIO.output(STEP1, GPIO.LOW)
            GPIO.output(STEP2, GPIO.LOW)
            time.sleep(delay)
        print(f"Motors 1 and 2 completed {rotations} rotations.")
    
    elif motor == '3':
        enable_motor3()
        GPIO.output(DIR3, GPIO.HIGH if direction else GPIO.LOW)
        for step in range(steps):
            GPIO.output(STEP3, GPIO.HIGH)
            time.sleep(delay)
            GPIO.output(STEP3, GPIO.LOW)
            time.sleep(delay)
        print(f"Motor 3 completed {rotations} rotations.")
    
    disable_all_motors()

def cleanup():
    disable_all_motors()
    GPIO.cleanup()

# Example Usage
try:
    motor_choice = input("Select motor to move (1_2 for motors 1 and 2, 3 for motor 3): ").strip()
    user_speed = float(input("Enter speed in RPM (e.g., 60): "))
    user_direction = input("Enter direction (f for forward, b for backward): ").lower() == 'f'
    user_rotations = int(input("Enter number of rotations: "))
    
    move_motor(motor_choice, user_direction, user_speed, user_rotations)

except KeyboardInterrupt:
    print("\nProcess interrupted.")

finally:
    cleanup()
