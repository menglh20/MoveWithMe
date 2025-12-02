# python common libraries
import time
import random
import board
# accelerometer
import adafruit_adxl34x
# neopixel
import neopixel
# bus
import busio
import i2cdisplaybus
# display
import displayio
import terminalio
from adafruit_display_text import label
import adafruit_displayio_ssd1306
# button and rotary encoder
import digitalio
from rotary_encoder import RotaryEncoder


# ========= PIN DEFINITIONS =========
ENC_A_PIN = board.D7      # Rotary encoder A
ENC_B_PIN = board.D8      # Rotary encoder B
ENC_SW_PIN = board.D9     # Encoder push button (with pull-up)

# ========= I2C & DEVICES INIT (OLED + ACCEL) =========
displayio.release_displays()
i2c = busio.I2C(board.SCL, board.SDA)

# OLED
display_bus = i2cdisplaybus.I2CDisplayBus(i2c, device_address=0x3C)
display = adafruit_displayio_ssd1306.SSD1306(display_bus, width=128, height=64)

# ACCELEROMETER
accelerometer = adafruit_adxl34x.ADXL345(i2c)

# ========= ROTARY ENCODER INIT  =========
encoder = RotaryEncoder(ENC_A_PIN, ENC_B_PIN,
                        debounce_ms=3, pulses_per_detent=3)

# Button
button = digitalio.DigitalInOut(ENC_SW_PIN)
button.switch_to_input(pull=digitalio.Pull.UP)  # ACTIVE LOW

# ------------- Debounce State (timer-based) -------------
last_state = button.value       # immediate raw reading from last loop
stable_state = button.value     # debounced (accepted) state
last_time = time.monotonic()
debounceDelay = 0.05


def button_fell():
    """
    Return True exactly once when the button is PRESSED (debounced falling edge).
    Uses the same timer-based debounce logic as your example.
    """
    global last_state, stable_state, last_time

    current_state = button.value
    now = time.monotonic()

    # If raw state changed, mark the time of this potential transition
    if current_state != last_state:
        last_time = now
        last_state = current_state

    # If the raw state has stayed unchanged longer than debounceDelay,
    # accept it as the new stable state and trigger events accordingly.
    if (now - last_time) > debounceDelay:
        if stable_state != current_state:
            # We have a debounced state change
            stable_state = current_state

            if not stable_state:
                # stable_state == False means button is PRESSED (fell edge)
                return True

    return False


# ========= NEOPIXEL INIT =========
NUM_PIXELS = 1
BRIGHTNESS = 0.3

pixels = neopixel.NeoPixel(
    board.D0, NUM_PIXELS, brightness=BRIGHTNESS, auto_write=False
)

# Some convenient color constants
COLOR_OFF = (0,   0,   0)
COLOR_RED = (255, 0,   0)
COLOR_GREEN = (0, 255,   0)
COLOR_BLUE = (0,   0, 255)
COLOR_YELLOW = (255, 255, 0)


def show_color(rgb):
    pixels[0] = rgb
    pixels.show()


# ========= ACCEL MOVEMENT DETECTION (EVENT-BASED) =========
THRESHOLD = 5          # m/s^2 to consider movement
REQUIRED_READS = 2     # consecutive loops required to confirm a direction
ALPHA = 0.20           # EMA smoothing factor
THRESH_OFF = THRESHOLD * 0.6

USE_BASELINE = True
BASELINE_SAMPLES = 100
BASELINE_DELAY = 0.02

# Baseline and filtered values
bx = by = bz = 0.0
xf = yf = zf = 0.0

# Direction state
candidate_dir = None
candidate_count = 0
active_dir = None  # currently confirmed movement direction


def ema(prev, raw, alpha=ALPHA):
    return alpha * raw + (1.0 - alpha) * prev


def axis_dir_from_values(x, y, z):
    """Pick dominant axis and return dir_code in {+X,-X,+Y,-Y,+Z,-Z} and magnitude."""
    ax_vals = [("X", x), ("Y", y), ("Z", z)]
    axis, val = max(ax_vals, key=lambda t: abs(t[1]))
    sign = "+" if val >= 0 else "-"
    return f"{sign}{axis}", abs(val)


def poll_movement_event():
    """
    Poll accelerometer once, update filters & state.
    Return dir_code of new movement event if detected, else None.
    Possible dir_code: {+X,-X,+Y,-Y,+Z,-Z}
    """
    global xf, yf, zf, candidate_dir, candidate_count, active_dir

    # ---- Read & baseline removal ----
    x, y, z = accelerometer.acceleration
    if USE_BASELINE:
        x -= bx
        y -= by
        z -= bz

    # ---- EMA filtering ----
    xf = ema(xf, x)
    yf = ema(yf, y)
    zf = ema(zf, z)

    # ---- Dominant axis ----
    dir_code, dom_val = axis_dir_from_values(xf, yf, zf)

    # ---- Hysteresis & dwell ----
    if active_dir:
        # movement is active; wait until it calms down below THRESH_OFF
        if dom_val <= THRESH_OFF:
            active_dir = None
        # no new event while still active
        return None
    else:
        if dom_val >= THRESHOLD:
            # count consecutive readings in same direction
            if dir_code == candidate_dir:
                candidate_count += 1
            else:
                candidate_dir = dir_code
                candidate_count = 1

            if candidate_count >= REQUIRED_READS:
                # Confirm new movement event
                active_dir = candidate_dir
                candidate_dir = None
                candidate_count = 0
                return active_dir
        else:
            # below threshold -> reset candidate
            candidate_dir = None
            candidate_count = 0
            return None


# ========= UI FUNCTIONS =========
def wait_for_button():
    """Block until debounced button press."""
    while True:
        if button_fell():
            time.sleep(0.2)
            return
        time.sleep(0.01)


def create_difficulty_screen(difficulties, selected_index):
    """Return a Group that draws difficulty menu."""
    group = displayio.Group()

    title = label.Label(
        terminalio.FONT, text="Select Difficulty", x=5, y=10
    )
    group.append(title)

    base_y = 25
    spacing = 15

    for i, diff in enumerate(difficulties):
        txt = label.Label(
            terminalio.FONT,
            text=diff,
            x=20,
            y=base_y + i * spacing,
        )
        group.append(txt)

        if i == selected_index:
            arrow = label.Label(
                terminalio.FONT,
                text=">",
                x=8,
                y=base_y + i * spacing,
            )
            group.append(arrow)

    return group


def show_difficulty_screen(selected_index):
    """Show the difficulty screen."""
    difficulties = ["EASY", "MEDIUM", "HARD"]
    group = create_difficulty_screen(difficulties, selected_index)
    display.root_group = group


def show_welcome_screen():
    """Show a welcome screen with border, centered text, and wait for button press."""

    WIDTH = 128
    HEIGHT = 64

    group = displayio.Group()

    # ======== Draw border ========
    border_bitmap = displayio.Bitmap(WIDTH, HEIGHT, 2)
    border_palette = displayio.Palette(2)
    border_palette[0] = 0x000000  # black
    border_palette[1] = 0xFFFFFF  # white

    # Draw rectangle edges
    for x in range(WIDTH):
        border_bitmap[x, 0] = 1
        border_bitmap[x, HEIGHT - 1] = 1
    for y in range(HEIGHT):
        border_bitmap[0, y] = 1
        border_bitmap[WIDTH - 1, y] = 1

    border_tilegrid = displayio.TileGrid(
        border_bitmap, pixel_shader=border_palette)
    group.append(border_tilegrid)

    # ======== Centered text ========
    def center_text(text, y):
        """Helper: return a Label centered horizontally."""
        # average character width ≈ 6 px (for terminalio.FONT)
        text_width = len(text) * 6
        x = (WIDTH - text_width) // 2
        return label.Label(terminalio.FONT, text=text, x=x, y=y)

    group.append(center_text("Welcome To", 20))
    group.append(center_text("<Move With Me>", 35))
    group.append(center_text("Press button to start", 52))

    display.root_group = group

    wait_for_button()


def show_level_ready_screen(difficulty, level):
    group = displayio.Group()

    title = label.Label(
        terminalio.FONT,
        text=f"{difficulty}  L{level}",
        x=5,
        y=10
    )
    group.append(title)

    msg = label.Label(
        terminalio.FONT,
        text="Are you ready",
        x=5,
        y=30
    )
    group.append(msg)

    msg2 = label.Label(
        terminalio.FONT,
        text="for next level?",
        x=5,
        y=45
    )
    group.append(msg2)

    display.root_group = group


COMMAND_ARROW = {
    "FORWARD":  "^",
    "BACKWARD": "v",
    "LEFT":     "<",
    "RIGHT":    ">",
}


def show_single_command_screen(difficulty, level, command, step_index, total_steps):
    """
    Show screen for a single command in the sequence.
    Returns the timer_label so caller can update its text.
    """
    group = displayio.Group()

    # Header: difficulty + level
    header = label.Label(
        terminalio.FONT,
        text=f"{difficulty}  L{level}",
        x=5,
        y=10
    )
    group.append(header)

    # Step indicator
    step_text = f"Step {step_index + 1}/{total_steps}"
    step_label = label.Label(
        terminalio.FONT,
        text=step_text,
        x=5,
        y=25
    )
    group.append(step_label)

    # Current command arrow
    arrow_str = COMMAND_ARROW[command]  # get arrow symbol
    arrow_label = label.Label(
        terminalio.FONT,
        text=arrow_str,
        x=60,
        y=45,
    )
    group.append(arrow_label)

    # Countdown display (placeholder, will be updated in real-time)
    timer_label = label.Label(
        terminalio.FONT,
        text="Time: --s",
        x=5,
        y=60
    )
    group.append(timer_label)

    display.root_group = group

    # Return the timer_label so the caller can update its text
    return timer_label


def show_fail_screen(difficulty, level):
    group = displayio.Group()

    title = label.Label(
        terminalio.FONT,
        text="Level Failed",
        x=10,
        y=10
    )
    group.append(title)

    info = label.Label(
        terminalio.FONT,
        text=f"{difficulty}  L{level}",
        x=10,
        y=30
    )
    group.append(info)

    tip = label.Label(
        terminalio.FONT,
        text="Nice try! Press",
        x=10,
        y=45
    )
    group.append(tip)

    tip2 = label.Label(
        terminalio.FONT,
        text="button to retry",
        x=10,
        y=58
    )
    group.append(tip2)

    display.root_group = group
    show_color(COLOR_RED)


def show_congrats_screen(difficulty):
    group = displayio.Group()

    title = label.Label(
        terminalio.FONT,
        text="CONGRATULATIONS!",
        x=0,
        y=15
    )
    group.append(title)

    msg = label.Label(
        terminalio.FONT,
        text=f"You beat {difficulty}",
        x=5,
        y=35
    )
    group.append(msg)

    msg2 = label.Label(
        terminalio.FONT,
        text="Press button to menu",
        x=0,
        y=50
    )
    group.append(msg2)

    display.root_group = group


def show_calibration_screen_and_calibrate():
    """
    Show calibration screen with countdown, sample accelerometer to compute baseline.
    1. Show "Loading... Keep still for 5" screen
    2. Sample accelerometer for 5 seconds, compute baseline offsets
    """
    global bx, by, bz, xf, yf, zf, baseline_done

    WIDTH = 128
    HEIGHT = 64

    group = displayio.Group()

    def center_text(text, y):
        text_width = len(text) * 6
        x = (WIDTH - text_width) // 2
        return label.Label(terminalio.FONT, text=text, x=x, y=y)

    title = center_text("Loading...", 12)
    tip1 = center_text("Keep still for", 30)
    group.append(title)
    group.append(tip1)

    countdown_label = center_text("5", 46)
    group.append(countdown_label)

    display.root_group = group

    baseline_done = False
    sx = sy = sz = 0.0
    count = 0

    TOTAL_TIME = 5
    SAMPLE_DELAY = 0.02

    start = time.monotonic()
    last_second = 5  # for updating display

    while True:
        now = time.monotonic()
        elapsed = now - start
        remain = TOTAL_TIME - elapsed

        # Countdown number (integer seconds)
        sec = max(0, int(remain) + 1)
        if sec != last_second:
            countdown_label.text = str(sec)
            last_second = sec

        if elapsed >= TOTAL_TIME:
            break

        # Sample accelerometer
        x, y, z = accelerometer.acceleration
        sx += x
        sy += y
        sz += z
        count += 1

        time.sleep(SAMPLE_DELAY)

    # Finished sampling, compute baseline
    if count > 0:
        bx = sx / count
        by = sy / count
        bz = sz / count

    # Initialize filtered values
    x0, y0, z0 = accelerometer.acceleration
    x0 -= bx
    y0 -= by
    z0 -= bz
    xf = x0
    yf = y0
    zf = z0

    baseline_done = True
    print(f"Baseline calibrated: bx={bx}, by={by}, bz={bz}")


# ========= MAIN GAME LOGIC =========
def select_difficulty():
    difficulties = ["EASY", "MEDIUM", "HARD"]

    selected = 0  # start at EASY
    last_pos = encoder.position

    show_difficulty_screen(selected)

    # encoder move "cooldown": minimum time between menu steps
    STEP_INTERVAL = 0.08  # 80 ms, you can tune this (0.05 ~ 0.1)
    last_step_time = time.monotonic()

    # movement accumulation for step detection
    move_accum = 0
    STEP_THRESHOLD = 2

    while True:
        now = time.monotonic()

        # --- Rotary encoder update ---
        changed = encoder.update()
        if changed:
            pos = encoder.position
            delta = pos - last_pos
            last_pos = pos

            # Accumulate absolute value, direction doesn't matter
            move_accum += abs(delta)

            # Only switch difficulty when accumulated steps are enough and time interval is sufficient
            if (now - last_step_time) > STEP_INTERVAL and move_accum >= STEP_THRESHOLD:
                # Always move in one direction: EASY -> MEDIUM -> HARD -> EASY ->
                selected = (selected + 1) % len(difficulties)
                show_difficulty_screen(selected)

                last_step_time = now      # reset cooldown timer
                move_accum = 0           # reset accumulation for next step

        if button_fell():
            # confirmed selection
            time.sleep(0.2)
            return difficulties[selected]

        time.sleep(0.001)


def dir_code_to_command(dir_code):
    """
    Map accelerometer dir_code to game command.
    Returns one of {"FORWARD","BACKWARD","LEFT","RIGHT"} or None if we ignore it.
    """
    if dir_code == "+Y":
        return "LEFT"
    elif dir_code == "-Y":
        return "RIGHT"
    elif dir_code == "-X":
        return "BACKWARD"
    elif dir_code == "+X":
        return "FORWARD"
    else:
        # ignore Z axis or other
        return None


def get_time_limit(difficulty):
    if difficulty == "EASY":
        return 10.0
    elif difficulty == "MEDIUM":
        return 5.0
    elif difficulty == "HARD":
        return 3.0
    else:
        return 5.0


ALL_COMMANDS = ["FORWARD", "BACKWARD", "LEFT", "RIGHT"]


def generate_command_sequence(level):
    length = level + 2
    return [random.choice(ALL_COMMANDS) for _ in range(length)]


def play_one_level(difficulty, level):
    """
    Play one level of the game.
    Returns True if passed, False if failed.
    1. Show "Get Ready" screen, wait for button
    2. For each command in sequence:
        a. Show command screen
        b. Start timer
        c. Wait for first movement event
            - If correct command within time limit: pass, short green light
            - Else: fail, red light, return False
    3. If all commands passed: return True
    4. Overall time limit per command depends on difficulty
    """
    time_limit = get_time_limit(difficulty)   # EASY=10s, MED=5s, HARD=1s
    commands = generate_command_sequence(level)
    total_steps = len(commands)

    # Step 1: Show "Get Ready" screen and wait for button
    show_level_ready_screen(difficulty, level)
    show_color(COLOR_BLUE)  # ready state
    wait_for_button()

    # Complete each command in sequence
    for idx, cmd in enumerate(commands):
        # Show current command screen
        timer_label = show_single_command_screen(
            difficulty, level, cmd, idx, total_steps)
        show_color(COLOR_YELLOW)  # current command in progress

        # Start timer for each command
        start_time = time.monotonic()

        # Wait for the first movement of this command
        while True:
            now = time.monotonic()
            elapsed = now - start_time

            remaining = time_limit - elapsed

            # Update countdown display (integer seconds for clarity)
            if remaining < 0:
                remaining = 0
            # For example: Time: 3s
            timer_label.text = f"Time: {int(remaining)}s"

            # Level timeout → fail
            if elapsed > time_limit:
                show_color(COLOR_RED)
                return False

            # Poll accelerometer events
            dir_code = poll_movement_event()
            if dir_code:
                move_cmd = dir_code_to_command(dir_code)

                # We only care about the four directions on the X/Y axes; ignore others (e.g., Z)
                if move_cmd is None:
                    # Ignore this movement, keep waiting
                    pass
                else:
                    # "Within the time limit, the first movement must match the current command"
                    if move_cmd != cmd:
                        print("move_cmd:" + move_cmd + ", cmd:" + cmd)
                        show_color(COLOR_RED)
                        return False
                    else:
                        # This command is correct; pass with a short green light before continuing to the next command
                        show_color(COLOR_GREEN)
                        time.sleep(1)
                        # Break out of the while loop to proceed to the next command
                        break

            time.sleep(0.01)

    # If the for loop completes successfully, all commands were completed correctly and within the time limit
    show_color(COLOR_GREEN)
    return True


def blink_congrats_led():
    on = False
    while True:
        if on:
            show_color(COLOR_GREEN)
        else:
            show_color(COLOR_OFF)
        on = not on

        # Also check the button during blinking
        for _ in range(10):
            if button_fell():
                time.sleep(0.2)
                return
            time.sleep(0.02)


def play_game(difficulty):
    MAX_LEVEL = 10
    for level in range(1, MAX_LEVEL + 1):
        passed = play_one_level(difficulty, level)
        if not passed:
            show_fail_screen(difficulty, level)
            wait_for_button()   # Press to return to difficulty selection
            return  # Game over, return to main() to reselect difficulty

    # If we reach here, it means levels 1-10 were all passed
    show_congrats_screen(difficulty)
    blink_congrats_led()  # Press button to exit
    # Return to main()


def main():
    show_color(COLOR_BLUE)
    show_welcome_screen()
    while True:
        show_color(COLOR_YELLOW)

        difficulty = select_difficulty()

        show_calibration_screen_and_calibrate()

        play_game(difficulty)


main()
