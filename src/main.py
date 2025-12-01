import time
import math
import random
import board
import adafruit_adxl34x
import neopixel
import busio
import displayio
import terminalio
from adafruit_display_text import label
import i2cdisplaybus
import adafruit_displayio_ssd1306
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
encoder = RotaryEncoder(ENC_A_PIN, ENC_B_PIN, debounce_ms=3, pulses_per_detent=3)

# Button
button = digitalio.DigitalInOut(ENC_SW_PIN)
button.switch_to_input(pull=digitalio.Pull.UP)  # ACTIVE LOW

# ------------- Debounce State (timer-based) -------------
last_state = button.value       # immediate raw reading from last loop
stable_state = button.value     # debounced (accepted) state
last_time = time.monotonic()
debounceDelay = 0.05           # 50 ms is a good start

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
COLOR_OFF    = (0,   0,   0)
COLOR_RED    = (255, 0,   0)
COLOR_GREEN  = (0, 255,   0)
COLOR_BLUE   = (0,   0, 255)
COLOR_YELLOW = (255, 255, 0)

def show_color(rgb):
    pixels[0] = rgb
    pixels.show()
    
    
# ========= ACCEL MOVEMENT DETECTION (EVENT-BASED) =========
THRESHOLD = 5        # m/s^2 to consider movement
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
    如果检测到一个新的“确认方向事件”，返回 dir_code（例如 '+X','-Y'），否则返回 None。
    """
    global xf, yf, zf, candidate_dir, candidate_count, active_dir

    # ---- Read & baseline removal ----
    x, y, z = accelerometer.acceleration
    if USE_BASELINE:
        x -= bx; y -= by; z -= bz

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

    border_tilegrid = displayio.TileGrid(border_bitmap, pixel_shader=border_palette)
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

    # ======== Wait for button press ========
    while True:
        if button_fell():
            time.sleep(0.2)
            break
        time.sleep(0.01)
        
def wait_for_button():
    """Block until debounced button press."""
    while True:
        if button_fell():
            time.sleep(0.2)
            return
        time.sleep(0.01)

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

def show_commands_screen(difficulty, level, commands):
    """Show difficulty, level and arrow sequence for current level."""
    group = displayio.Group()

    header = label.Label(
        terminalio.FONT,
        text=f"{difficulty}  L{level}",
        x=5,
        y=10
    )
    group.append(header)

    msg = label.Label(
        terminalio.FONT,
        text="Do moves:",
        x=5,
        y=25
    )
    group.append(msg)

    arrow_str = "".join(COMMAND_ARROW[c] for c in commands)
    arrows = label.Label(
        terminalio.FONT,
        text=arrow_str,
        x=5,
        y=45
    )
    group.append(arrows)

    display.root_group = group

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
    显示“加载中 + 5 秒倒计时”，并在这 5 秒期间采集 baseline 数据。
    玩家看到的画面会显示每秒变化的倒计时。
    """
    global bx, by, bz, xf, yf, zf, baseline_done

    WIDTH = 128
    HEIGHT = 64

    # ==== 创建画面 Group ====
    group = displayio.Group()

    def center_text(text, y):
        text_width = len(text) * 6
        x = (WIDTH - text_width) // 2
        return label.Label(terminalio.FONT, text=text, x=x, y=y)

    # 固定文本：提示保持不动
    title = center_text("Loading...", 12)
    tip1 = center_text("Keep still for", 30)
    group.append(title)
    group.append(tip1)

    # 动态文本：倒计时数字（稍后更新）
    countdown_label = center_text("5", 46)
    group.append(countdown_label)

    display.root_group = group

    # ==== baseline 采样 ====
    baseline_done = False
    sx = sy = sz = 0.0
    count = 0

    # 倒计时总时长
    TOTAL_TIME = 5
    SAMPLE_DELAY = 0.02

    start = time.monotonic()
    last_second = 5  # 上一次显示的倒计时数字

    while True:
        now = time.monotonic()
        elapsed = now - start
        remain = TOTAL_TIME - elapsed

        # 倒计时数字（取整数秒）
        sec = max(0, int(remain) + 1)
        if sec != last_second:
            countdown_label.text = str(sec)
            last_second = sec

        if elapsed >= TOTAL_TIME:
            break

        # 采样加速度计
        x, y, z = accelerometer.acceleration
        sx += x
        sy += y
        sz += z
        count += 1

        time.sleep(SAMPLE_DELAY)

    # ==== 完成采样，计算 baseline ====
    if count > 0:
        bx = sx / count
        by = sy / count
        bz = sz / count

    # 初始化滤波值
    x0, y0, z0 = accelerometer.acceleration
    x0 -= bx; y0 -= by; z0 -= bz
    xf = x0; yf = y0; zf = z0

    baseline_done = True
    print(f"Baseline calibrated: bx={bx}, by={by}, bz={bz}")




# ========= MAIN SELECTION LOGIC =========
def select_difficulty():
    difficulties = ["EASY", "MEDIUM", "HARD"]

    selected = 0  # start at EASY
    last_pos = encoder.position

    show_difficulty_screen(selected)

    # encoder move "cooldown": minimum time between menu steps
    STEP_INTERVAL = 0.08  # 80 ms, you can tune this (0.05 ~ 0.1)
    last_step_time = time.monotonic()

    # 累积旋转量（绝对值），大于一定阈值才算“转了一格”
    move_accum = 0
    STEP_THRESHOLD = 2  # 可以调成 2 看手感

    while True:
        now = time.monotonic()

        # --- Rotary encoder update ---
        changed = encoder.update()
        if changed:
            pos = encoder.position
            delta = pos - last_pos
            last_pos = pos

            # 累加绝对值，不在乎方向
            move_accum += abs(delta)

            # 只有在累计步数够、并且时间间隔够的时候才切换一次难度
            if (now - last_step_time) > STEP_INTERVAL and move_accum >= STEP_THRESHOLD:
                # 统一只往一个方向走：EASY -> MEDIUM -> HARD -> EASY ->
                selected = (selected + 1) % len(difficulties)
                show_difficulty_screen(selected)

                last_step_time = now      # reset cooldown timer
                move_accum = 0           # 重新累计下一格

        # --- Debounced button press (falling edge) ---
        if button_fell():
            # confirmed selection
            time.sleep(0.2)
            return difficulties[selected]

        time.sleep(0.001)



def show_final_screen(text):
    """Display some text on screen."""
    group = displayio.Group()
    lbl = label.Label(terminalio.FONT, text=text, x=10, y=30)
    group.append(lbl)
    display.root_group = group
    

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

COMMAND_ARROW = {
    "FORWARD":  "^",
    "BACKWARD": "v",
    "LEFT":     "<",
    "RIGHT":    ">",
}

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

def show_single_command_screen(difficulty, level, command, step_index, total_steps):
    """
    显示当前难度、关卡、当前指令（一个箭头）、当前是第几步，
    并返回一个倒计时用的 Label，方便外面实时更新文本。
    """
    group = displayio.Group()

    # 头部：难度 + 关卡
    header = label.Label(
        terminalio.FONT,
        text=f"{difficulty}  L{level}",
        x=5,
        y=10
    )
    group.append(header)

    # Step 信息
    step_text = f"Step {step_index + 1}/{total_steps}"
    step_label = label.Label(
        terminalio.FONT,
        text=step_text,
        x=5,
        y=25
    )
    group.append(step_label)

    # 当前指令箭头
    arrow_str = COMMAND_ARROW[command]  # 例如 "^" "<" ">" "v"
    arrow_label = label.Label(
        terminalio.FONT,
        text=arrow_str,
        x=60,
        y=45,
    )
    group.append(arrow_label)

    # 倒计时显示（先写一个占位，后面实时更新）
    timer_label = label.Label(
        terminalio.FONT,
        text="Time: --s",
        x=5,
        y=60
    )
    group.append(timer_label)

    display.root_group = group

    # 把 timer_label 返回，外面可以不断改它的 text
    return timer_label



def play_one_level(difficulty, level):
    """
    一次只显示一个指令：
    - 本关随机生成 level+2 条指令
    - 屏幕一次显示一条
    - 玩家在总时间限制内依次完成所有指令
    - 对每条指令：在时间内检测到的“第一个有效 movement”必须匹配当前指令，否则失败
    - 任意一条失败或总时间超时：整关失败
    - 全部指令在时间限制内完成：成功
    """
    time_limit = get_time_limit(difficulty)   # EASY=10s, MED=5s, HARD=1s
    commands = generate_command_sequence(level)
    total_steps = len(commands)

    # Step 1: 准备界面 + 等待按钮
    show_level_ready_screen(difficulty, level)
    show_color(COLOR_BLUE)  # ready 状态
    wait_for_button()

    # 依次完成每一条指令
    for idx, cmd in enumerate(commands):
        # 显示当前指令
        timer_label = show_single_command_screen(difficulty, level, cmd, idx, total_steps)
        show_color(COLOR_YELLOW)  # 当前指令执行中
        
        # 每条指令单独开始计时
        start_time = time.monotonic()

        # 等待这一条指令的第一次 movement
        while True:
            now = time.monotonic()
            elapsed = now - start_time
            
            remaining = time_limit - elapsed

            # 更新倒计时显示（取整秒，更清晰）
            if remaining < 0:
                remaining = 0
            # 例如：Time: 3s
            timer_label.text = f"Time: {int(remaining)}s"

            # 整个 level 超时 → 失败
            if elapsed > time_limit:
                show_color(COLOR_RED)
                return False

            # 轮询加速度计事件
            dir_code = poll_movement_event()
            if dir_code:
                move_cmd = dir_code_to_command(dir_code)

                # 我们只关心 X/Y 四个方向，其他（比如 Z）忽略
                if move_cmd is None:
                    # 忽略这次 movement，继续等
                    pass
                else:
                    # “在时间要求内，第一个movement必须符合当前指令”
                    if move_cmd != cmd:
                        print("move_cmd:" + move_cmd + ", cmd:" + cmd)
                        show_color(COLOR_RED)
                        return False
                    else:
                        # 这一条指令正确，通过；短暂亮绿再继续下一条
                        show_color(COLOR_GREEN)
                        time.sleep(1)
                        # 跳出 while，进入下一条指令
                        break

            time.sleep(0.01)

    # 如果 for 循环顺利结束，说明所有指令都正确完成且未超时
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

        # 在闪烁期间也要检测按钮
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
            wait_for_button()   # 按下回到难度选择
            return  # 游戏结束，回 main() 重新选难度

    # 如果能跑到这里，说明 1-10 全部通过
    show_congrats_screen(difficulty)
    blink_congrats_led()  # 按按钮退出
    # 返回 main()


def main():
    show_color(COLOR_BLUE)
    show_welcome_screen()
    while True:
        show_color(COLOR_YELLOW)
        
        difficulty = select_difficulty()
        
        show_calibration_screen_and_calibrate()
        
        play_game(difficulty)


main()